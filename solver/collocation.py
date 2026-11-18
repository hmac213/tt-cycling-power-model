"""Stage 2 of the optimizer: polish a plan by direct transcription.

The dynamic program can only pick powers and states from its grids. This
stage removes that rounding. Speed, reserve, and power at every grid node
become unknowns of one large sparse nonlinear program, the dynamics become
constraints linking neighbouring nodes, and IPOPT solves it with exact
derivatives from CasADi. It is a local method, which is why it starts from
the dynamic program's globally chosen plan.

Unknowns, for a grid of n steps:

    v_k    speed at node k                            k = 1..n
    x_k    reserve deficit 1 - B_k / W' at node k     k = 1..n
    r_k    power below CP on step k, as a share of CP k = 0..n-1
    e_k    power above CP on step k, as a share of CP k = 0..n-1

so that P_k = CP (1 - r_k + e_k). Splitting the power this way keeps the
stamina law smooth: draining depends only on e and recovery only on r.

Constraints:

    v_{k+1}^3 <= v_k^3 advanced by RK4 at power P_k      (motion)
    x_{k+1}    = recover(x_k, r_k, dt_k) + e_k CP dt_k / W'   (stamina)
    v_{k+1}   <= corner speed cap of step k
    0 <= x_k <= 1,  0 <= r_k <= 1,  0 <= e_k <= P_max / CP - 1

The motion constraint is an inequality because the rider may brake: the gap
between the two sides is the kinetic energy braked away. The transcription
uses the same RK4 substeps, time rule, and stamina update as the simulator, so
the plan is checked afterwards by simply simulating it.
"""

import dataclasses

import casadi as ca
import numpy as np

from physics_model import params as physics_params
from power_model import params as rider_params
from solver import simulate

# The deficit never goes below this, as in power_model/cp_model.py.
_MIN_DEFICIT = 1e-12


@dataclasses.dataclass(frozen=True)
class PolishResult:
    """Outcome of the collocation stage.

    Attributes:
        ride: The polished plan, as ridden by the simulator.
        converged: Whether IPOPT reported an optimal solution.
        message: IPOPT's return status.
        iterations: Number of IPOPT iterations.
    """

    ride: simulate.RideResult
    converged: bool
    message: str
    iterations: int


def supports(rider: rider_params.RiderParams) -> bool:
    """Tells whether the split-power formulation is exact for a rider.

    With P = CP (1 - r + e) the program could in principle set r and e both
    positive on one step. That never pays as long as a watt of recovery
    returns at most a joule per second, i.e. alpha <= 1. For alpha > 1 the
    program could manufacture reserve, so the stage is skipped.

    Args:
        rider: Rider parameters.

    Returns:
        True if the collocation stage can be used.
    """
    return rider.alpha <= 1.0


def _next_deficit(
    deficit: ca.SX,
    below: ca.SX,
    above: ca.SX,
    duration: ca.SX,
    rider: rider_params.RiderParams,
) -> ca.SX:
    """Advances the deficit x = 1 - B/W' over one step.

    Mirrors `cp_model.step_reserve`: recovery follows the closed-form
    solution of dx/dt = -k x^beta, and expenditure adds linearly.
    """
    rate = rider.alpha * rider.cp * below / rider.w_prime
    if rider.beta == 1.0:
        recovered = deficit * ca.exp(-rate * duration)
    else:
        exponent = 1.0 - rider.beta
        base = ca.fmax(deficit, _MIN_DEFICIT) ** exponent
        base = base - exponent * rate * duration
        if exponent > 0:
            base = ca.fmax(base, 0.0)
        recovered = base ** (1.0 / exponent)
    return recovered + rider.cp * above * duration / rider.w_prime


def polish(
    start: simulate.RideResult,
    grid: simulate.RideGrid,
    physics: physics_params.PhysicsParams,
    rider: rider_params.RiderParams,
    config: simulate.SimConfig,
    max_iterations: int = 1000,
    tolerance: float = 1e-8,
) -> PolishResult:
    """Refines a pacing plan with IPOPT.

    Args:
        start: The ride to start from, on the same grid.
        grid: The course grid.
        physics: Physical parameters.
        rider: Rider parameters.
        config: Grid settings.
        max_iterations: Iteration cap for IPOPT.
        tolerance: IPOPT convergence tolerance.

    Returns:
        The polished ride and IPOPT's status.

    Raises:
        ValueError: If the rider is not supported; see `supports`.
    """
    if not supports(rider):
        raise ValueError("The collocation stage needs alpha <= 1.")
    num_steps = grid.num_steps
    speed_floor = config.min_speed**3
    max_above = rider.p_max / rider.cp - 1.0
    # Typical size of v^3, to bring the motion constraints to order one.
    speed_scale = float(np.mean(start.speed)) ** 3

    def to_speed(speed_cubed: ca.SX) -> ca.SX:
        return ca.fmax(speed_cubed, speed_floor) ** (1.0 / 3.0)

    speed = ca.SX.sym("v", num_steps)
    deficit = ca.SX.sym("x", num_steps)
    below = ca.SX.sym("r", num_steps)
    above = ca.SX.sym("e", num_steps)

    total_time = 0.0
    motion = []
    stamina = []
    for k in range(num_steps):
        start_speed = grid.start_speed if k == 0 else speed[k - 1]
        start_deficit = 0.0 if k == 0 else deficit[k - 1]
        power = rider.cp * (1.0 - below[k] + above[k])
        trajectory = simulate.free_trajectory(
            start_speed**3, power, grid.theta[k], grid.headwind[k],
            grid.step, physics, to_speed,
        )
        free_cubed = trajectory[-1]
        duration = simulate.step_duration(
            simulate.braked_speeds(
                start_speed, trajectory, speed[k], to_speed
            ),
            grid.step,
        )
        total_time += duration
        motion.append((free_cubed - speed[k] ** 3) / speed_scale)
        stamina.append(
            deficit[k]
            - _next_deficit(start_deficit, below[k], above[k], duration, rider)
        )

    problem = {
        "x": ca.vertcat(speed, deficit, below, above),
        "f": total_time / start.total_time,
        "g": ca.vertcat(*motion, *stamina),
    }
    solver = ca.nlpsol("pacing", "ipopt", problem, {
        "print_time": False,
        "ipopt": {
            "print_level": 0,
            "sb": "yes",
            "max_iter": max_iterations,
            "tol": tolerance,
            "mu_init": 1e-3,
            "bound_push": 1e-6,
            "bound_frac": 1e-6,
        },
    })

    start_ratio = start.power / rider.cp
    guess = np.concatenate([
        np.clip(start.speed[1:], config.min_speed, grid.speed_cap),
        np.clip(1.0 - start.reserve[1:] / rider.w_prime, 0.0, 1.0),
        np.clip(1.0 - start_ratio, 0.0, 1.0),
        np.clip(start_ratio - 1.0, 0.0, max_above),
    ])
    zeros = np.zeros(num_steps)
    solution = solver(
        x0=guess,
        lbx=np.concatenate(
            [np.full(num_steps, config.min_speed), zeros, zeros, zeros]
        ),
        ubx=np.concatenate([
            grid.speed_cap,
            np.ones(num_steps),
            np.ones(num_steps),
            np.full(num_steps, max_above),
        ]),
        lbg=np.zeros(2 * num_steps),
        ubg=np.concatenate([np.full(num_steps, np.inf), zeros]),
    )

    values = np.asarray(solution["x"]).ravel()
    below_value = values[2 * num_steps:3 * num_steps]
    above_value = values[3 * num_steps:]
    plan = np.clip(
        rider.cp * (1.0 - below_value + above_value), 0.0, rider.p_max
    )
    stats = solver.stats()
    return PolishResult(
        ride=simulate.simulate(plan, grid, physics, rider, config),
        converged=bool(stats["success"]),
        message=str(stats["return_status"]),
        iterations=int(stats["iter_count"]),
    )
