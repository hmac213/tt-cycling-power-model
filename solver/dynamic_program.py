"""Stage 1 of the optimizer: dynamic programming over (distance, speed, B).

The value function J_k(v, B) is the least time needed to reach the finish
from grid node k at speed v with reserve B. It obeys

    J_n(v, B) = 0,
    J_k(v, B) = min over P of  dt(v, P) + J_{k+1}(v', B'),   B' >= 0,

where (v', B') is the state after riding step k at power P. Tabulating J
backwards from the finish on a grid of speeds and reserves, and trying every
power level at every grid point, examines every plan the grids can express.
The result is therefore a global optimum, up to the resolution of the grids,
with no starting guess involved.

The plan is then read off by riding forwards from the start line and picking,
at every step, the power that minimizes dt + J_{k+1}. The forward ride uses
the exact state, not a rounded one, so the plan it returns is feasible.
"""

import dataclasses

import numpy as np

from physics_model import params as physics_params
from power_model import cp_model
from power_model import params as rider_params
from solver import simulate

# Head room of the speed grid above the fastest speed reachable at P_max.
_SPEED_MARGIN = 1.02

# A reserve this far below zero [J] still counts as empty, not overdrawn.
_RESERVE_SLACK = 1e-6


@dataclasses.dataclass(frozen=True)
class DpConfig:
    """Resolution of the dynamic program.

    Attributes:
        num_speeds: Number of speed grid points.
        num_reserves: Number of reserve grid points between 0 and W'.
        num_powers: Number of power levels between 0 and P_max tried when
            tabulating J. CP is always one of them.
        rollout_refinement: The forward ride tries this many times more
            power levels than the table was built with.
    """

    num_speeds: int = 80
    num_reserves: int = 60
    num_powers: int = 25
    rollout_refinement: int = 4


@dataclasses.dataclass(frozen=True)
class _Tables:
    """State grids of the dynamic program.

    Attributes:
        speeds: Speed grid [m/s], uniform.
        reserves: Reserve grid [J], uniform from 0 to W'.
    """

    speeds: np.ndarray
    reserves: np.ndarray


def power_levels(
    rider: rider_params.RiderParams, num_levels: int
) -> np.ndarray:
    """Builds the power levels to try, with CP exactly on the list.

    Riding at exactly CP is the one power that leaves B unchanged, so it
    must be available. The levels are evenly spaced below CP and evenly
    spaced above it.

    Args:
        rider: Rider parameters.
        num_levels: Total number of levels, at least 3.

    Returns:
        Increasing power levels from 0 to P_max [W].
    """
    below = int(round((num_levels - 1) * rider.cp / rider.p_max))
    below = min(max(below, 1), num_levels - 2)
    above = num_levels - 1 - below
    return np.concatenate([
        np.linspace(0.0, rider.cp, below + 1),
        np.linspace(rider.cp, rider.p_max, above + 1)[1:],
    ])


def _interpolate(
    value: np.ndarray,
    tables: _Tables,
    speed: np.ndarray,
    reserve: np.ndarray,
) -> np.ndarray:
    """Interpolates a value table bilinearly at the given states."""
    speeds, reserves = tables.speeds, tables.reserves
    speed_pos = (speed - speeds[0]) / (speeds[1] - speeds[0])
    speed_pos = np.clip(speed_pos, 0.0, speeds.size - 1.0)
    reserve_pos = reserve / (reserves[1] - reserves[0])
    reserve_pos = np.clip(reserve_pos, 0.0, reserves.size - 1.0)
    i = np.minimum(speed_pos.astype(int), speeds.size - 2)
    j = np.minimum(reserve_pos.astype(int), reserves.size - 2)
    a = speed_pos - i
    b = reserve_pos - j
    return (
        (1 - a) * (1 - b) * value[i, j]
        + a * (1 - b) * value[i + 1, j]
        + (1 - a) * b * value[i, j + 1]
        + a * b * value[i + 1, j + 1]
    )


def _time_to_finish(
    speed: np.ndarray,
    reserve: np.ndarray,
    powers: np.ndarray,
    index: int,
    value_next: np.ndarray,
    tables: _Tables,
    grid: simulate.RideGrid,
    physics: physics_params.PhysicsParams,
    rider: rider_params.RiderParams,
    config: simulate.SimConfig,
) -> np.ndarray:
    """Evaluates dt + J_{k+1} for every (speed, reserve, power) combination.

    Args:
        speed: Speeds at the start of the step [m/s], shape (S,).
        reserve: Reserves at the start of the step [J], shape (R,).
        powers: Power levels to try [W], shape (U,).
        index: Which grid step is being ridden.
        value_next: J at the end of the step, on the state grid.
        tables: The state grids.
        grid: The course grid.
        physics: Physical parameters.
        rider: Rider parameters.
        config: Grid settings.

    Returns:
        Time to the finish [s], shape (S, R, U); infinite where the power
        would overdraw the reserve.
    """
    end_speed, duration, _ = simulate.advance(
        speed[:, None], powers[None, :], index, grid, physics, config
    )
    end_reserve = cp_model.step_reserve(
        reserve[None, :, None],
        powers[None, None, :],
        duration[:, None, :],
        cp_model.at_step(rider, index),
    )
    rest = _interpolate(
        value_next, tables, end_speed[:, None, :], end_reserve
    )
    total = duration[:, None, :] + rest
    return np.where(end_reserve >= -_RESERVE_SLACK, total, np.inf)


def solve(
    grid: simulate.RideGrid,
    physics: physics_params.PhysicsParams,
    rider: rider_params.RiderParams,
    config: simulate.SimConfig,
    dp_config: DpConfig = DpConfig(),
) -> simulate.RideResult:
    """Finds the globally best pacing plan the grids can express.

    Args:
        grid: The course grid.
        physics: Physical parameters.
        rider: Rider parameters.
        config: Grid settings.
        dp_config: Resolution of the dynamic program.

    Returns:
        The ride produced by the plan.
    """
    # No plan can go faster than full power everywhere.
    flat_out = simulate.simulate_batch(
        np.full(grid.num_steps, rider.p_max), grid, physics, rider, config
    )[0]
    tables = _Tables(
        speeds=np.linspace(
            config.min_speed,
            _SPEED_MARGIN * flat_out.max(),
            dp_config.num_speeds,
        ),
        reserves=np.linspace(0.0, rider.w_prime, dp_config.num_reserves),
    )
    powers = power_levels(rider, dp_config.num_powers)

    # Backward pass: tabulate J at every node.
    value = np.zeros(
        (grid.num_steps + 1, tables.speeds.size, tables.reserves.size),
        dtype=np.float32,
    )
    for k in range(grid.num_steps - 1, -1, -1):
        total = _time_to_finish(
            tables.speeds, tables.reserves, powers, k, value[k + 1],
            tables, grid, physics, rider, config,
        )
        value[k] = total.min(axis=-1)

    # Forward pass: ride from the start, choosing the best power each step.
    fine_powers = power_levels(
        rider, (dp_config.num_powers - 1) * dp_config.rollout_refinement + 1
    )
    plan = np.empty(grid.num_steps)
    speed = np.array([grid.start_speed])
    reserve = np.array([rider.w_prime])
    for k in range(grid.num_steps):
        total = _time_to_finish(
            speed, reserve, fine_powers, k, value[k + 1],
            tables, grid, physics, rider, config,
        )
        plan[k] = fine_powers[int(np.argmin(total[0, 0]))]
        speed, duration, _ = simulate.advance(
            speed, plan[k], k, grid, physics, config
        )
        reserve = np.maximum(
            cp_model.step_reserve(
                reserve, plan[k], duration, cp_model.at_step(rider, k)
            ),
            0.0,
        )
    return simulate.simulate(plan, grid, physics, rider, config)
