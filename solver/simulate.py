"""Forward simulation: given a power plan, ride the course.

The course is cut into steps of one fixed length (20 m by default), and power
is constant on each step. The simulator and both optimization stages share
this grid. Inside a step the speed is advanced with a few RK4 substeps (5 m
each by default) that read slope and wind from the course as they go, so the
dynamics stay accurate even when the speed changes a lot within one step.

Cornering is enforced here too. The speed is capped by the latest-braking
envelope (see physics_model/cornering.py), and whatever kinetic energy the
cap removes is counted as braking. Pedalling into a corner therefore wastes
energy, and it is up to the power plan to ease off or coast beforehand.

Distance is the independent variable, so the finish line is a fixed endpoint
and the race time is simply an output.
"""

import dataclasses
from typing import Any, Callable, Sequence

import numpy as np
from numpy import typing as npt

from course_loader import course as course_lib
from physics_model import cornering
from physics_model import dynamics
from physics_model import params as physics_params
from power_model import cp_model
from power_model import params as rider_params

_DEFAULT_PHYSICS = physics_params.PhysicsParams()
_DEFAULT_RIDER = rider_params.RiderParams()

# A ride counts as feasible if B stays above this fraction of W' below zero.
_FEASIBILITY_TOLERANCE = 1e-6


@dataclasses.dataclass(frozen=True)
class SimConfig:
    """Settings of the grid shared by the simulator and the optimizers.

    Attributes:
        step_length: Target length of one grid step [m]. The actual step is
            the course length divided by a whole number of steps, so it is
            this long or slightly shorter.
        substeps: Number of RK4 substeps per grid step.
        initial_speed: Speed at the start line [m/s]; 0 is a standing start.
        min_speed: Speed floor [m/s], which keeps dt = ds/v finite if the
            rider stalls.
        corner_window: Length over which curvature is averaged before it is
            turned into a cornering speed limit [m].
    """

    step_length: float = 20.0
    substeps: int = 4
    initial_speed: float = 0.0
    min_speed: float = 0.5
    corner_window: float = 20.0


_DEFAULT_CONFIG = SimConfig()


@dataclasses.dataclass(frozen=True)
class RideGrid:
    """The fixed-length grid of one course.

    Slope and wind are stored at every RK4 stage point: the start, middle,
    and end of each of the m substeps of a step, 2m + 1 points in all.

    Attributes:
        nodes: Step boundaries [m], shape (n + 1,).
        step: Step length [m].
        substeps: RK4 substeps per step, m.
        theta: Incline at the stage points [rad], shape (n, 2m + 1).
        headwind: Headwind at the stage points [m/s], shape (n, 2m + 1).
        speed_cap: Lowest envelope speed over each step [m/s], shape (n,).
            It limits the speed at the end of the step.
        start_speed: Speed at the start line [m/s].
    """

    nodes: np.ndarray
    step: float
    substeps: int
    theta: np.ndarray
    headwind: np.ndarray
    speed_cap: np.ndarray
    start_speed: float

    @property
    def num_steps(self) -> int:
        """Number of grid steps n."""
        return self.nodes.size - 1


@dataclasses.dataclass(frozen=True)
class RideResult:
    """Outcome of riding a course with a given power plan.

    Attributes:
        distance: Grid nodes [m], shape (n + 1,).
        power: Power on each step [W], shape (n,).
        speed: Speed at each node [m/s], shape (n + 1,).
        time: Elapsed time at each node [s], shape (n + 1,).
        reserve: Anaerobic reserve B at each node [J], shape (n + 1,).
        brake_energy: Kinetic energy removed by braking on each step [J],
            shape (n,).
    """

    distance: np.ndarray
    power: np.ndarray
    speed: np.ndarray
    time: np.ndarray
    reserve: np.ndarray
    brake_energy: np.ndarray

    @property
    def total_time(self) -> float:
        """Race time T [s]."""
        return float(self.time[-1])

    @property
    def feasible(self) -> bool:
        """Whether the reserve B stays nonnegative for the whole ride."""
        tolerance = _FEASIBILITY_TOLERANCE * max(1.0, self.reserve[0])
        return bool(self.reserve.min() >= -tolerance)


def course_speed_envelope(
    course: course_lib.Course,
    physics: physics_params.PhysicsParams = _DEFAULT_PHYSICS,
    config: SimConfig = _DEFAULT_CONFIG,
) -> np.ndarray:
    """Computes the latest-braking speed envelope of a course.

    Args:
        course: The course.
        physics: Physical parameters.
        config: Grid settings; only `corner_window` is used.

    Returns:
        The envelope speed [m/s] at every sample of the course.
    """
    curvature = course.mean_curvature(config.corner_window)
    corner_speed = cornering.corner_speed_limit(
        curvature, course.theta, physics
    )
    return cornering.speed_envelope(
        course.distance, corner_speed, course.theta, course.headwind, physics
    )


def build_grid(
    course: course_lib.Course,
    physics: physics_params.PhysicsParams = _DEFAULT_PHYSICS,
    config: SimConfig = _DEFAULT_CONFIG,
) -> RideGrid:
    """Cuts a course into fixed-length steps.

    Args:
        course: The course.
        physics: Physical parameters.
        config: Grid settings.

    Returns:
        The grid, with slope, wind, and speed caps precomputed.
    """
    # A course a hair over a whole number of steps does not get an extra one.
    num_steps = max(1, int(np.ceil(course.length / config.step_length - 1e-3)))
    nodes = np.linspace(0.0, course.length, num_steps + 1)
    step = course.length / num_steps
    stages = nodes[:-1, None] + np.linspace(0.0, step, 2 * config.substeps + 1)

    # Cap each step at the lowest envelope value among the course samples in
    # (start, end], so that a corner shorter than one step is still seen.
    envelope = course_speed_envelope(course, physics, config)
    envelope = np.maximum(envelope, config.min_speed)
    first = np.searchsorted(course.distance, nodes[:-1], side="right")
    first = np.minimum(first, envelope.size - 1)
    speed_cap = np.minimum.reduceat(envelope, first)

    start_speed = min(max(config.initial_speed, 0.0), float(envelope[0]))
    return RideGrid(
        nodes=nodes,
        step=step,
        substeps=config.substeps,
        theta=course.theta_at(stages),
        headwind=course.wind_at(stages),
        speed_cap=speed_cap,
        start_speed=start_speed,
    )


def free_trajectory(
    speed_cubed: Any,
    power: Any,
    theta: Sequence[float],
    headwind: Sequence[float],
    step: float,
    physics: physics_params.PhysicsParams,
    to_speed: Callable[[Any], Any],
) -> list[Any]:
    """Advances z = v^3 over one grid step with no braking.

    Each substep is classical RK4 on dz/ds = (3/m)(P - v F_res). The code
    uses plain arithmetic only, so it runs on numpy arrays (the simulator
    and the dynamic program) and on CasADi expressions (the collocation
    stage) alike.

    Args:
        speed_cubed: v^3 at the start of the step [m^3/s^3].
        power: Constant power over the step [W].
        theta: Incline at the 2m + 1 stage points of the step [rad].
        headwind: Headwind at the same points [m/s].
        step: Step length [m].
        physics: Physical parameters.
        to_speed: Maps v^3 to v, with whatever floor the caller applies.

    Returns:
        v^3 at 2m evenly spaced points after the start: the middle and the
        end of every substep. The last entry is the end of the step. The
        midpoints come from the third-order continuous extension of RK4, so
        they cost no extra evaluations of the dynamics.
    """
    substeps = (len(theta) - 1) // 2
    length = step / substeps

    def rate(state: Any, stage: int) -> Any:
        return dynamics.speed_cubed_rate(
            to_speed(state), power, theta[stage], headwind[stage], physics
        )

    trajectory = []
    for i in range(substeps):
        k1 = rate(speed_cubed, 2 * i)
        k2 = rate(speed_cubed + 0.5 * length * k1, 2 * i + 1)
        k3 = rate(speed_cubed + 0.5 * length * k2, 2 * i + 1)
        k4 = rate(speed_cubed + length * k3, 2 * i + 2)
        trajectory.append(
            speed_cubed + length / 24.0 * (5 * k1 + 4 * k2 + 4 * k3 - k4)
        )
        speed_cubed = speed_cubed + length / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
        trajectory.append(speed_cubed)
    return trajectory


def braked_speeds(
    start_speed: Any,
    trajectory: Sequence[Any],
    end_speed: Any,
    to_speed: Callable[[Any], Any],
) -> list[Any]:
    """Builds the speed profile over a step that ends at a given speed.

    If the rider brakes, the step ends below the free trajectory. The v^3
    removed is taken to come off evenly along the step, so the rider slows
    down gradually and does not hold full speed until the last metre.

    Args:
        start_speed: Speed at the start of the step [m/s].
        trajectory: Free trajectory of v^3, from `free_trajectory`.
        end_speed: Actual speed at the end of the step [m/s].
        to_speed: Maps v^3 to v.

    Returns:
        Speeds at evenly spaced points from the start to the end of the
        step [m/s].
    """
    shed = trajectory[-1] - end_speed**3
    count = len(trajectory)
    speeds = [start_speed]
    for i, speed_cubed in enumerate(trajectory[:-1]):
        speeds.append(to_speed(speed_cubed - (i + 1) / count * shed))
    speeds.append(end_speed)
    return speeds


def step_duration(speeds: Sequence[Any], step: float) -> Any:
    """Computes the time taken to cover one grid step.

    Integrates ds/v piece by piece between the given speeds, with v^3 taken
    as linear in s on each piece. That is exact for pure acceleration from
    rest, where 1/v blows up.

    Args:
        speeds: Speeds at evenly spaced points from the start to the end of
            the step [m/s]. All but the first must be positive.
        step: Step length [m].

    Returns:
        The duration [s].
    """
    piece = step / (len(speeds) - 1)
    duration = 0.0
    for start, end in zip(speeds[:-1], speeds[1:]):
        duration = duration + 1.5 * piece * (start + end) / (
            start**2 + start * end + end**2
        )
    return duration


def advance(
    speed: np.ndarray,
    power: np.ndarray,
    index: int,
    grid: RideGrid,
    physics: physics_params.PhysicsParams,
    config: SimConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Rides one grid step, braking only if the corner limit demands it.

    Args:
        speed: Speed at the start of the step [m/s].
        power: Power over the step [W]; broadcasts against `speed`.
        index: Which grid step to ride.
        grid: The grid.
        physics: Physical parameters.
        config: Grid settings.

    Returns:
        Arrays (end_speed, duration, brake_energy) for the step.
    """
    floor = config.min_speed**3

    def to_speed(speed_cubed: np.ndarray) -> np.ndarray:
        return np.cbrt(np.maximum(speed_cubed, floor))

    trajectory = free_trajectory(
        speed**3, power, grid.theta[index], grid.headwind[index],
        grid.step, physics, to_speed,
    )
    free_speed = to_speed(trajectory[-1])
    trajectory[-1] = free_speed**3
    end_speed = np.minimum(free_speed, grid.speed_cap[index])
    brake_energy = 0.5 * physics.effective_mass * (free_speed**2 - end_speed**2)
    speeds = braked_speeds(speed, trajectory, end_speed, to_speed)
    return end_speed, step_duration(speeds, grid.step), brake_energy


def simulate_batch(
    power: npt.ArrayLike,
    grid: RideGrid,
    physics: physics_params.PhysicsParams = _DEFAULT_PHYSICS,
    rider: rider_params.RiderParams = _DEFAULT_RIDER,
    config: SimConfig = _DEFAULT_CONFIG,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Simulates one or many power plans at once.

    Args:
        power: Power on each grid step [W], shape (..., n).
        grid: The grid, with n steps.
        physics: Physical parameters.
        rider: Rider parameters.
        config: Grid settings.

    Returns:
        Arrays (speed, time, reserve, brake_energy). The first three hold
        values at the grid nodes, shape (..., n + 1). The last holds the
        energy braked away on each step, shape (..., n).

    Raises:
        ValueError: If the plan does not have one power per grid step.
    """
    power = np.asarray(power, float)
    if power.shape[-1] != grid.num_steps:
        raise ValueError(
            f"Expected {grid.num_steps} powers, got {power.shape[-1]}."
        )
    batch_shape = power.shape[:-1]
    speed = np.empty(batch_shape + (grid.num_steps + 1,))
    time = np.empty_like(speed)
    reserve = np.empty_like(speed)
    brake_energy = np.empty(batch_shape + (grid.num_steps,))

    speed[..., 0] = grid.start_speed
    time[..., 0] = 0.0
    reserve[..., 0] = rider.w_prime
    for i in range(grid.num_steps):
        step_power = power[..., i]
        speed[..., i + 1], duration, brake_energy[..., i] = advance(
            speed[..., i], step_power, i, grid, physics, config
        )
        time[..., i + 1] = time[..., i] + duration
        reserve[..., i + 1] = cp_model.step_reserve(
            reserve[..., i], step_power, duration, cp_model.at_step(rider, i)
        )
    return speed, time, reserve, brake_energy


def simulate(
    power: npt.ArrayLike,
    grid: RideGrid,
    physics: physics_params.PhysicsParams = _DEFAULT_PHYSICS,
    rider: rider_params.RiderParams = _DEFAULT_RIDER,
    config: SimConfig = _DEFAULT_CONFIG,
) -> RideResult:
    """Rides a course with one power per grid step.

    Args:
        power: Power on each grid step [W], shape (n,).
        grid: The grid, from `build_grid`.
        physics: Physical parameters.
        rider: Rider parameters.
        config: Grid settings.

    Returns:
        The resulting ride.
    """
    power = np.asarray(power, float)
    speed, time, reserve, brake_energy = simulate_batch(
        power, grid, physics, rider, config
    )
    return RideResult(
        distance=grid.nodes,
        power=power,
        speed=speed,
        time=time,
        reserve=reserve,
        brake_energy=brake_energy,
    )
