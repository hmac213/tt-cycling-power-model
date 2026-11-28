"""Stage 1 of the optimizer: dynamic programming.

The value function J_k(v, x, F) is the least time needed to reach the finish
from grid node k at speed v, with deficit x of the fast reserve and fatigue
F. It obeys

    J_n(v, x, F) = 0,
    J_k(v, x, F) = min over P of  dt(v, P) + J_{k+1}(v', x', F'),   x' <= 1,

where (v', x', F') is the state after riding step k at power P. Tabulating J
backwards from the finish on a grid of states, and trying every power level
at every grid point, examines every plan the grids can express. The result
is therefore a global optimum, up to the resolution of the grids, with no
starting guess involved.

The plan is then read off by riding forwards from the start line and picking,
at every step, the power that minimizes dt + J_{k+1}. The forward ride uses
the exact state, not a rounded one, so the plan it returns is feasible.

The fourth stamina state, the work done E, is not a dimension of the table.
E only sets the size W' of the fast reserve, and how much work has been done
by a given point on the course hardly depends on the pacing. So the table
is built with W' taken from a reference ride at each step, while the forward
ride tracks E exactly. If the two disagree by more than a small tolerance,
the table is rebuilt with the forward ride as the new reference.
"""

import dataclasses

import numpy as np
from scipy import ndimage

from physics_model import params as physics_params
from power_model import cp_model
from power_model import params as rider_params
from solver import simulate

# Head room of the speed grid above the fastest speed reachable at P_max.
_SPEED_MARGIN = 1.02

# A deficit this far above 1 still counts as empty, not overdrawn.
_DEFICIT_SLACK = 1e-9

# The fatigue grid reaches this many times the fatigue of the reference
# ride, but at least tau_F and at most _MAX_FATIGUE_TIMES tau_F. Beyond the
# latter, critical power sits on its floor and more fatigue changes nothing.
_FATIGUE_HEAD_ROOM = 4.0
_MAX_FATIGUE_TIMES = 2.5

# Rebuild the table if the reserve capacity along the forward ride differs
# from the reference by more than this fraction.
_CAPACITY_TOLERANCE = 0.01
_MAX_PASSES = 3


@dataclasses.dataclass(frozen=True)
class DpConfig:
    """Resolution of the dynamic program.

    Attributes:
        num_speeds: Number of speed grid points.
        num_deficits: Number of grid points for the deficit x in [0, 1].
        num_fatigues: Number of grid points for the fatigue F.
        num_powers: Number of power levels between 0 and P_max tried when
            tabulating J. LT1 and LT2 are always among them.
        rollout_refinement: The forward ride tries this many times more
            power levels than the table was built with.
    """

    num_speeds: int = 50
    num_deficits: int = 40
    num_fatigues: int = 12
    num_powers: int = 25
    rollout_refinement: int = 4


@dataclasses.dataclass(frozen=True)
class _Tables:
    """State grids of the dynamic program, each uniform.

    Attributes:
        speeds: Speed grid [m/s].
        deficits: Deficit grid [-], from 0 to 1.
        fatigues: Fatigue grid [s], from 0.
    """

    speeds: np.ndarray
    deficits: np.ndarray
    fatigues: np.ndarray


def power_levels(
    rider: rider_params.RiderParams, num_levels: int
) -> np.ndarray:
    """Builds the power levels to try, with LT1 and LT2 on the list.

    The levels are evenly spaced within each of the three intensity
    domains: below LT1, between the thresholds, and above LT2. Each domain
    gets a share of the levels in proportion to its width.

    Args:
        rider: Rider parameters.
        num_levels: Total number of levels, at least 4.

    Returns:
        Increasing power levels from 0 to P_max [W].
    """
    steps = num_levels - 1
    low = min(max(int(round(steps * rider.lt1 / rider.p_max)), 1), steps - 2)
    middle = int(round(steps * (rider.lt2 - rider.lt1) / rider.p_max))
    middle = min(max(middle, 1), steps - low - 1)
    high = steps - low - middle
    return np.concatenate([
        np.linspace(0.0, rider.lt1, low + 1),
        np.linspace(rider.lt1, rider.lt2, middle + 1)[1:],
        np.linspace(rider.lt2, rider.p_max, high + 1)[1:],
    ])


def _interpolate(
    value: np.ndarray,
    tables: _Tables,
    speed: np.ndarray,
    deficit: np.ndarray,
    fatigue: np.ndarray,
) -> np.ndarray:
    """Interpolates a value table linearly at the given states.

    States outside the grids are moved to the nearest edge.
    """
    shape = np.broadcast_shapes(speed.shape, deficit.shape, fatigue.shape)
    coordinates = np.empty((3,) + shape)
    for row, (axis, state) in enumerate((
        (tables.speeds, speed),
        (tables.deficits, deficit),
        (tables.fatigues, fatigue),
    )):
        coordinates[row] = (state - axis[0]) / (axis[1] - axis[0])
    return ndimage.map_coordinates(
        value, coordinates, order=1, mode="nearest"
    )


def _time_to_finish(
    speed: np.ndarray,
    deficit: np.ndarray,
    fatigue: np.ndarray,
    capacity: float,
    powers: np.ndarray,
    index: int,
    value_next: np.ndarray,
    tables: _Tables,
    grid: simulate.RideGrid,
    physics: physics_params.PhysicsParams,
    rider: rider_params.RiderParams,
    config: simulate.SimConfig,
) -> np.ndarray:
    """Evaluates dt + J_{k+1} for every combination of state and power.

    Args:
        speed: Speeds at the start of the step [m/s], shape (S,).
        deficit: Deficits at the start of the step [-], shape (R,).
        fatigue: Fatigues at the start of the step [s], shape (G,).
        capacity: Size W' of the fast reserve on this step [J].
        powers: Power levels to try [W], shape (U,).
        index: Which grid step is being ridden.
        value_next: J at the end of the step, on the state grid.
        tables: The state grids.
        grid: The course grid.
        physics: Physical parameters.
        rider: Rider parameters.
        config: Grid settings.

    Returns:
        Time to the finish [s], shape (S, R, G, U); infinite where the
        power would overdraw the reserve.
    """
    end_speed, duration, _ = simulate.advance(
        speed[:, None], powers[None, :], index, grid, physics, config
    )
    end_deficit = cp_model.step_deficit(
        deficit[None, :, None, None],
        powers[None, None, None, :],
        duration[:, None, None, :],
        cp_model.critical_power(fatigue, rider)[None, None, :, None],
        capacity,
        rider,
    )
    end_fatigue = (
        fatigue[None, :, None]
        + cp_model.fatigue_rate(powers, rider)[None, None, :]
        * duration[:, None, :]
    )
    rest = _interpolate(
        value_next,
        tables,
        end_speed[:, None, None, :],
        end_deficit,
        end_fatigue[:, None, :, :],
    )
    total = duration[:, None, None, :] + rest
    return np.where(end_deficit <= 1.0 + _DEFICIT_SLACK, total, np.inf)


def _fatigue_limit(
    rider: rider_params.RiderParams, reference: simulate.RideResult
) -> float:
    """Chooses the top of the fatigue grid."""
    limit = _FATIGUE_HEAD_ROOM * float(reference.fatigue[-1])
    if not np.isfinite(rider.fatigue_time):
        return max(limit, 1.0)
    return float(np.clip(
        limit, rider.fatigue_time, _MAX_FATIGUE_TIMES * rider.fatigue_time
    ))


def _one_pass(
    capacity: np.ndarray,
    tables: _Tables,
    grid: simulate.RideGrid,
    physics: physics_params.PhysicsParams,
    rider: rider_params.RiderParams,
    config: simulate.SimConfig,
    dp_config: DpConfig,
) -> np.ndarray:
    """Tabulates J for a given reserve capacity per step, then rides it.

    Returns:
        The power plan [W], shape (n,).
    """
    powers = power_levels(rider, dp_config.num_powers)
    value = np.zeros(
        (
            grid.num_steps + 1,
            tables.speeds.size,
            tables.deficits.size,
            tables.fatigues.size,
        ),
        dtype=np.float32,
    )
    for k in range(grid.num_steps - 1, -1, -1):
        total = _time_to_finish(
            tables.speeds, tables.deficits, tables.fatigues, capacity[k],
            powers, k, value[k + 1], tables, grid, physics, rider, config,
        )
        value[k] = total.min(axis=-1)

    # Forward ride from the start line, with the exact state.
    fine_powers = power_levels(
        rider, (dp_config.num_powers - 1) * dp_config.rollout_refinement + 1
    )
    plan = np.empty(grid.num_steps)
    speed = np.array([grid.start_speed])
    deficit = np.zeros(1)
    fatigue = np.zeros(1)
    work = np.zeros(1)
    for k in range(grid.num_steps):
        total = _time_to_finish(
            speed, deficit, fatigue,
            float(cp_model.reserve_capacity(work, rider)[0]),
            fine_powers, k, value[k + 1], tables, grid, physics, rider, config,
        )
        plan[k] = fine_powers[int(np.argmin(total[0, 0, 0]))]
        speed, duration, _ = simulate.advance(
            speed, plan[k], k, grid, physics, config
        )
        deficit, fatigue, work = cp_model.step_state(
            deficit, fatigue, work, plan[k], duration, rider
        )
        deficit = np.minimum(deficit, 1.0)
    return plan


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
    reference = simulate.best_constant_power(grid, physics, rider, config)
    # No plan can go faster than full power everywhere.
    flat_out = simulate.simulate(
        np.full(grid.num_steps, rider.p_max), grid, physics, rider, config
    )
    tables = _Tables(
        speeds=np.linspace(
            config.min_speed,
            _SPEED_MARGIN * flat_out.speed.max(),
            dp_config.num_speeds,
        ),
        deficits=np.linspace(0.0, 1.0, dp_config.num_deficits),
        fatigues=np.linspace(
            0.0, _fatigue_limit(rider, reference), dp_config.num_fatigues
        ),
    )

    capacity = reference.capacity
    for _ in range(_MAX_PASSES):
        plan = _one_pass(
            capacity, tables, grid, physics, rider, config, dp_config
        )
        ride = simulate.simulate(plan, grid, physics, rider, config)
        mismatch = np.max(np.abs(ride.capacity / capacity - 1.0))
        if mismatch <= _CAPACITY_TOLERANCE:
            break
        capacity = ride.capacity
    return ride
