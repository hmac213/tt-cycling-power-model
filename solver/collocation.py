"""Stage 2 of the optimizer: polish a plan by direct transcription.

The dynamic program can only pick powers and states from its grids. This
stage removes that rounding. The state and power at every grid node become
unknowns of one large sparse nonlinear program, the dynamics become
constraints linking neighbouring nodes, and IPOPT solves it with exact
derivatives from CasADi. It is a local method, which is why it starts from
the dynamic program's globally chosen plan.

Unknowns, for a grid of n steps:

    v_k    speed at node k                            k = 1..n
    x_k    deficit of the fast reserve at node k      k = 1..n
    F_k    fatigue at node k                          k = 1..n
    E_k    work done at node k                        k = 1..n
    P_k    power on step k                            k = 0..n-1
    e_k    power above critical power on step k       k = 0..n-1

Constraints, with CP_k and W'_k the critical power and reserve capacity
that follow from F_k and E_k:

    v_{k+1}^3 <= v_k^3 advanced by RK4 at power P_k              (motion)
    x_{k+1}    = recover(x_k, CP_k - P_k + e_k) + e_k dt_k / W'_k  (stamina)
    F_{k+1}    = F_k + fatigue_rate(P_k) dt_k                    (fatigue)
    E_{k+1}    = E_k + P_k dt_k                                  (work)
    e_k       >= P_k - CP_k                                      (split)
    v_{k+1}   <= corner speed cap of step k
    0 <= x_k <= 1,  0 <= P_k <= P_max,  e_k >= 0

The motion constraint is an inequality because the rider may brake: the gap
between the two sides is the kinetic energy braked away.

The split keeps the stamina law smooth across P = CP. Draining depends only
on e, and recovery only on the power below critical power, CP - P + e. At
the optimum e is as small as allowed, e = max(P - CP, 0), which makes the
two pieces the usual expenditure and recovery laws.

The transcription uses the same RK4 substeps, time rule, and stamina update
as the simulator, so the plan is checked afterwards by simply simulating it.
"""

import dataclasses

import casadi as ca
import numpy as np

from physics_model import params as physics_params
from power_model import cp_model
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

    The program could in principle set e above max(P - CP, 0), which drains
    and recovers at the same time. That never pays as long as a watt of
    recovery returns at most a joule per second, i.e. alpha <= 1. For
    alpha > 1 the program could manufacture reserve, so the stage is
    skipped.

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
    capacity: ca.SX,
    rider: rider_params.RiderParams,
) -> ca.SX:
    """Advances the deficit x over one step.

    Mirrors `cp_model.step_deficit`: recovery follows the closed-form
    solution of dx/dt = -k x^beta, and expenditure adds linearly.

    Args:
        deficit: Deficit at the start of the step [-].
        below: Power below critical power [W].
        above: Power above critical power [W].
        duration: Duration of the step [s].
        capacity: Size W' of the fast reserve on the step [J].
        rider: Rider parameters.

    Returns:
        Deficit at the end of the step [-].
    """
    rate = rider.alpha * below / capacity
    if rider.beta == 1.0:
        recovered = deficit * ca.exp(-rate * duration)
    else:
        exponent = 1.0 - rider.beta
        base = ca.fmax(deficit, _MIN_DEFICIT) ** exponent
        base = base - exponent * rate * duration
        if exponent > 0:
            base = ca.fmax(base, 0.0)
        recovered = base ** (1.0 / exponent)
    return recovered + above * duration / capacity


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
    # Scales that bring every unknown and constraint to order one.
    power_scale = rider.lt2
    speed_scale = float(np.mean(start.speed)) ** 3
    fatigue_scale = max(float(start.fatigue[-1]), 1.0)
    work_scale = max(float(start.work[-1]), 1.0)
    max_power = rider.p_max / power_scale

    def to_speed(speed_cubed: ca.SX) -> ca.SX:
        return ca.fmax(speed_cubed, speed_floor) ** (1.0 / 3.0)

    speed = ca.SX.sym("v", num_steps)
    deficit = ca.SX.sym("x", num_steps)
    fatigue = ca.SX.sym("f", num_steps)
    work = ca.SX.sym("w", num_steps)
    power = ca.SX.sym("p", num_steps)
    above = ca.SX.sym("e", num_steps)

    total_time = 0.0
    motion, stamina, tiring, working, split = [], [], [], [], []
    for k in range(num_steps):
        start_speed = grid.start_speed if k == 0 else speed[k - 1]
        start_deficit = 0.0 if k == 0 else deficit[k - 1]
        start_fatigue = 0.0 if k == 0 else fatigue_scale * fatigue[k - 1]
        start_work = 0.0 if k == 0 else work_scale * work[k - 1]
        watts = power_scale * power[k]
        watts_above = power_scale * above[k]
        cp = cp_model.critical_power(start_fatigue, rider, ca.exp)
        capacity = cp_model.reserve_capacity(start_work, rider, ca.exp)

        trajectory = simulate.free_trajectory(
            start_speed**3, watts, grid.theta[k], grid.headwind[k],
            grid.step, physics, to_speed,
        )
        duration = simulate.step_duration(
            simulate.braked_speeds(
                start_speed, trajectory, speed[k], to_speed
            ),
            grid.step,
        )
        total_time += duration
        motion.append((trajectory[-1] - speed[k] ** 3) / speed_scale)
        stamina.append(
            deficit[k]
            - _next_deficit(
                start_deficit, cp - watts + watts_above, watts_above,
                duration, capacity, rider,
            )
        )
        tiring.append(
            fatigue[k]
            - (start_fatigue + cp_model.fatigue_rate(watts, rider) * duration)
            / fatigue_scale
        )
        working.append(
            work[k] - (start_work + watts * duration) / work_scale
        )
        split.append(above[k] - power[k] + cp / power_scale)

    problem = {
        "x": ca.vertcat(speed, deficit, fatigue, work, power, above),
        "f": total_time / start.total_time,
        "g": ca.vertcat(*motion, *split, *stamina, *tiring, *working),
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

    zeros = np.zeros(num_steps)
    ones = np.ones(num_steps)
    infinite = np.full(num_steps, np.inf)
    start_power = start.power / power_scale
    start_cp = start.critical_power[:-1] / power_scale
    guess = np.concatenate([
        np.clip(start.speed[1:], config.min_speed, grid.speed_cap),
        np.clip(start.deficit[1:], 0.0, 1.0),
        start.fatigue[1:] / fatigue_scale,
        start.work[1:] / work_scale,
        np.clip(start_power, 0.0, max_power),
        np.clip(start_power - start_cp, 0.0, max_power),
    ])
    solution = solver(
        x0=guess,
        lbx=np.concatenate(
            [np.full(num_steps, config.min_speed), zeros, zeros, zeros,
             zeros, zeros]
        ),
        ubx=np.concatenate([
            grid.speed_cap, ones, infinite, infinite,
            np.full(num_steps, max_power), np.full(num_steps, max_power),
        ]),
        lbg=np.zeros(5 * num_steps),
        ubg=np.concatenate([infinite, infinite, zeros, zeros, zeros]),
    )

    values = np.asarray(solution["x"]).ravel()
    plan = np.clip(
        power_scale * values[4 * num_steps:5 * num_steps], 0.0, rider.p_max
    )
    stats = solver.stats()
    return PolishResult(
        ride=simulate.simulate(plan, grid, physics, rider, config),
        converged=bool(stats["success"]),
        message=str(stats["return_status"]),
        iterations=int(stats["iter_count"]),
    )
