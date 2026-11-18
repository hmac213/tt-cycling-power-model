"""Pacing optimization: find the power plan that minimizes race time.

    minimize    T(P_1, ..., P_n)
    subject to  0 <= P_k <= P_max,  B_k >= 0,  v_k <= V(s_k)

with one power per fixed-length grid step. It runs in two stages:

1. `dynamic_program.solve` searches every plan its grids can express, so it
   lands in the right basin without a starting guess, but its answer is
   rounded to those grids.
2. `collocation.polish` starts from that answer and removes the rounding
   with a local, continuous solver.
"""

import dataclasses

import numpy as np
from scipy import optimize

from course_loader import course as course_lib
from physics_model import params as physics_params
from power_model import params as rider_params
from solver import collocation
from solver import dynamic_program
from solver import simulate

_DEFAULT_PHYSICS = physics_params.PhysicsParams()
_DEFAULT_RIDER = rider_params.RiderParams()
_DEFAULT_CONFIG = simulate.SimConfig()
_DEFAULT_DP_CONFIG = dynamic_program.DpConfig()

# Tolerance [W] of the constant-power root find.
_POWER_TOLERANCE = 1e-6


@dataclasses.dataclass(frozen=True)
class OptimizeResult:
    """Outcome of a pacing optimization.

    Attributes:
        ride: The best ride found.
        dp_ride: The ride from the dynamic program alone (stage 1).
        polished: Whether `ride` is the collocation result (stage 2). When
            False, `ride` is `dp_ride`.
        message: What happened in stage 2.
    """

    ride: simulate.RideResult
    dp_ride: simulate.RideResult
    polished: bool
    message: str


def constant_power_ride(
    course: course_lib.Course,
    physics: physics_params.PhysicsParams = _DEFAULT_PHYSICS,
    rider: rider_params.RiderParams = _DEFAULT_RIDER,
    config: simulate.SimConfig = _DEFAULT_CONFIG,
) -> simulate.RideResult:
    """Finds the best constant power plan.

    This is the power that empties W' exactly at the finish. It is the naive
    pacing strategy and the benchmark that the optimizer must beat.

    Args:
        course: The course.
        physics: Physical parameters.
        rider: Rider parameters.
        config: Grid settings.

    Returns:
        The ride at that constant power.
    """
    grid = simulate.build_grid(course, physics, config)

    def final_reserve(power: float) -> float:
        plan = np.full(grid.num_steps, power)
        reserve = simulate.simulate_batch(plan, grid, physics, rider, config)[2]
        return float(reserve[-1])

    if final_reserve(rider.p_max) >= 0:
        best_power = rider.p_max
    else:
        best_power = optimize.brentq(
            final_reserve, rider.cp, rider.p_max, xtol=_POWER_TOLERANCE
        )
        # Land on the feasible side of the root.
        while final_reserve(best_power) < 0:
            best_power -= _POWER_TOLERANCE
    plan = np.full(grid.num_steps, best_power)
    return simulate.simulate(plan, grid, physics, rider, config)


def optimize_pacing(
    course: course_lib.Course,
    physics: physics_params.PhysicsParams = _DEFAULT_PHYSICS,
    rider: rider_params.RiderParams = _DEFAULT_RIDER,
    config: simulate.SimConfig = _DEFAULT_CONFIG,
    dp_config: dynamic_program.DpConfig = _DEFAULT_DP_CONFIG,
    polish: bool = True,
) -> OptimizeResult:
    """Solves the minimum-time pacing problem on a course.

    The polished plan is kept only if the simulator confirms that it is
    feasible and no slower than the dynamic program's plan. Otherwise the
    dynamic program's plan is returned.

    Args:
        course: The course.
        physics: Physical parameters.
        rider: Rider parameters.
        config: Grid settings.
        dp_config: Resolution of the dynamic program.
        polish: Whether to run the collocation stage.

    Returns:
        The best ride found, the stage 1 ride, and the status of stage 2.
    """
    grid = simulate.build_grid(course, physics, config)
    dp_ride = dynamic_program.solve(grid, physics, rider, config, dp_config)

    if not polish:
        return OptimizeResult(dp_ride, dp_ride, False, "polish not requested")
    if not collocation.supports(rider):
        return OptimizeResult(
            dp_ride, dp_ride, False, "polish skipped: needs alpha <= 1"
        )

    result = collocation.polish(dp_ride, grid, physics, rider, config)
    status = f"IPOPT {result.message}, {result.iterations} iterations"
    if not result.ride.feasible:
        return OptimizeResult(
            dp_ride, dp_ride, False, f"polish rejected, infeasible ({status})"
        )
    if result.ride.total_time > dp_ride.total_time:
        return OptimizeResult(
            dp_ride, dp_ride, False, f"polish rejected, slower ({status})"
        )
    return OptimizeResult(result.ride, dp_ride, True, status)
