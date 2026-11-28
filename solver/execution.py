"""Riding a plan imperfectly: power errors and unexpected weather.

The optimizer assumes the rider hits every power target exactly and that
the course and weather are known in advance. Here the rider tries to follow
a fixed plan but

* misses each target by a random error (`power_noise`), and/or
* rides in different conditions from the ones the plan was made for (pass a
  grid built from a course with different wind).

The rider still cannot spend reserve they do not have. On any step where the
requested power would take B below zero, they ride the largest power that
leaves B at zero instead (never less than their current critical power),
which is what an exhausted rider is forced to do. Many rides are simulated
at once as a batch.
"""

import dataclasses

import numpy as np
from numpy import typing as npt

from physics_model import params as physics_params
from power_model import cp_model
from power_model import params as rider_params
from solver import simulate

# Bisection steps for the exhaustion cap; 30 halvings resolve it to < 1e-6 W.
_CAP_ITERATIONS = 30


@dataclasses.dataclass(frozen=True)
class BatchRide:
    """Many imperfect rides of one plan.

    Attributes:
        distance: Grid nodes [m], shape (n + 1,).
        power: Power actually ridden [W], shape (k, n).
        speed: Speed at each node [m/s], shape (k, n + 1).
        time: Elapsed time at each node [s], shape (k, n + 1).
        reserve: Fast reserve B at each node [J], shape (k, n + 1).
        critical_power: Current critical power at each node [W], shape
            (k, n + 1).
        exhausted: Fraction of steps on which the rider had to back off
            because the reserve was empty, shape (k,).
    """

    distance: np.ndarray
    power: np.ndarray
    speed: np.ndarray
    time: np.ndarray
    reserve: np.ndarray
    critical_power: np.ndarray
    exhausted: np.ndarray

    @property
    def total_time(self) -> np.ndarray:
        """Finish time of each ride [s], shape (k,)."""
        return self.time[:, -1]

    def split_times(self, distances: npt.ArrayLike) -> np.ndarray:
        """Elapsed time at given distances [s], shape (k, len(distances))."""
        distances = np.atleast_1d(np.asarray(distances, float))
        return np.stack(
            [np.interp(distances, self.distance, row) for row in self.time]
        )


def power_noise(
    num_rides: int,
    num_steps: int,
    step: float,
    sigma: float,
    correlation_length: float = 200.0,
    bias: float = 0.0,
    seed: int = 0,
) -> np.ndarray:
    """Draws relative power errors that drift smoothly along the course.

    The error on step k is e_k = bias + x_k, where x is a stationary AR(1)
    process with standard deviation sigma and correlation length
    `correlation_length`. Riders do not jump randomly between targets every
    20 m; they drift above or below them for a while.

    Args:
        num_rides: Number of rides k.
        num_steps: Number of grid steps n.
        step: Grid step length [m].
        sigma: Standard deviation of the relative error, e.g. 0.05 for 5%.
        correlation_length: Distance over which errors stay similar [m].
        bias: Systematic relative error, e.g. 0.03 for riding 3% too hard.
        seed: Random seed.

    Returns:
        Relative errors, shape (k, n).
    """
    rng = np.random.default_rng(seed)
    rho = np.exp(-step / correlation_length) if correlation_length > 0 else 0.0
    shocks = rng.standard_normal((num_rides, num_steps))
    errors = np.empty_like(shocks)
    errors[:, 0] = sigma * shocks[:, 0]
    innovation = sigma * np.sqrt(1.0 - rho**2)
    for k in range(1, num_steps):
        errors[:, k] = rho * errors[:, k - 1] + innovation * shocks[:, k]
    return bias + errors


def ride_plan(
    plan: npt.ArrayLike,
    grid: simulate.RideGrid,
    physics: physics_params.PhysicsParams,
    rider: rider_params.RiderParams,
    config: simulate.SimConfig = simulate.SimConfig(),
    relative_error: npt.ArrayLike | None = None,
) -> BatchRide:
    """Rides a plan with power errors, backing off when exhausted.

    Args:
        plan: Target power on each step [W], shape (n,).
        grid: Grid of the course as actually ridden (its wind may differ
            from the one the plan was made for).
        physics: Physical parameters.
        rider: Rider parameters.
        config: Grid settings.
        relative_error: Relative power errors, shape (k, n), for example
            from `power_noise`. None rides the plan exactly once.

    Returns:
        The rides.
    """
    plan = np.asarray(plan, float)
    if relative_error is None:
        relative_error = np.zeros((1, plan.size))
    relative_error = np.atleast_2d(relative_error)
    num_rides, num_steps = relative_error.shape
    if num_steps != grid.num_steps or plan.size != num_steps:
        raise ValueError("plan, errors, and grid must have the same steps")

    target = np.clip(plan * (1.0 + relative_error), 0.0, rider.p_max)
    speed = np.empty((num_rides, num_steps + 1))
    time = np.zeros_like(speed)
    deficit = np.zeros_like(speed)
    fatigue = np.zeros_like(speed)
    work = np.zeros_like(speed)
    power = np.empty((num_rides, num_steps))
    capped = np.zeros((num_rides, num_steps), bool)
    speed[:, 0] = grid.start_speed

    for i in range(num_steps):

        def outcome(p):
            end_speed, duration, _ = simulate.advance(
                speed[:, i], p, i, grid, physics, config
            )
            state = cp_model.step_state(
                deficit[:, i], fatigue[:, i], work[:, i], p, duration, rider
            )
            return end_speed, duration, state

        p = target[:, i]
        end_speed, duration, state = outcome(p)
        short = state[0] > 1.0
        if short.any():
            # Largest power in [CP, target] that leaves B >= 0, by
            # bisection. Riding at the current CP leaves B unchanged.
            low = cp_model.critical_power(fatigue[:, i], rider)
            high = p.copy()
            for _ in range(_CAP_ITERATIONS):
                middle = 0.5 * (low + high)
                ok = outcome(middle)[2][0] <= 1.0
                low = np.where(ok, middle, low)
                high = np.where(ok, high, middle)
            p = np.where(short, np.minimum(low, p), p)
            capped[:, i] = short
            end_speed, duration, state = outcome(p)
        power[:, i] = p
        speed[:, i + 1] = end_speed
        time[:, i + 1] = time[:, i] + duration
        deficit[:, i + 1] = np.minimum(state[0], 1.0)
        fatigue[:, i + 1] = state[1]
        work[:, i + 1] = state[2]

    return BatchRide(
        distance=grid.nodes,
        power=power,
        speed=speed,
        time=time,
        reserve=(1.0 - deficit) * cp_model.reserve_capacity(work, rider),
        critical_power=cp_model.critical_power(fatigue, rider),
        exhausted=capped.mean(axis=1),
    )
