"""Longitudinal equation of motion of the bike.

    m dv/dt = P/v - 1/2 rho CdA (v + w)|v + w|
              - Crr m g cos(theta) - m g sin(theta)

Every function broadcasts over numpy arrays. The force functions use only
plain arithmetic on speed and power, so they also accept CasADi expressions,
which is how the collocation solver reuses them.
"""

import numpy as np
from numpy import typing as npt
from scipy import optimize

from physics_model import params


def aero_force(
    speed: npt.ArrayLike,
    headwind: npt.ArrayLike,
    physics: params.PhysicsParams,
) -> np.ndarray:
    """Computes the aerodynamic drag force.

    Args:
        speed: Bike speed [m/s].
        headwind: Wind speed opposing the rider [m/s]; negative is a tailwind.
        physics: Physical parameters.

    Returns:
        Drag force [N]. Negative when a tailwind is faster than the rider.
    """
    air_speed = speed + headwind
    return 0.5 * physics.rho * physics.cda * air_speed * abs(air_speed)


def rolling_force(
    theta: npt.ArrayLike,
    physics: params.PhysicsParams,
) -> np.ndarray:
    """Computes the rolling resistance force.

    Args:
        theta: Road incline angle [rad].
        physics: Physical parameters.

    Returns:
        Rolling resistance [N].
    """
    return physics.crr * physics.mass * physics.g * np.cos(theta)


def gravity_force(
    theta: npt.ArrayLike,
    physics: params.PhysicsParams,
) -> np.ndarray:
    """Computes the component of weight along the road.

    Args:
        theta: Road incline angle [rad].
        physics: Physical parameters.

    Returns:
        Gravity force opposing motion [N]; positive uphill.
    """
    return physics.mass * physics.g * np.sin(theta)


def resistive_force(
    speed: npt.ArrayLike,
    theta: npt.ArrayLike,
    headwind: npt.ArrayLike,
    physics: params.PhysicsParams,
) -> np.ndarray:
    """Computes the total force opposing motion.

    Args:
        speed: Bike speed [m/s].
        theta: Road incline angle [rad].
        headwind: Wind speed opposing the rider [m/s].
        physics: Physical parameters.

    Returns:
        F_air + F_rr + F_grav [N].
    """
    return (
        aero_force(speed, headwind, physics)
        + rolling_force(theta, physics)
        + gravity_force(theta, physics)
    )


def acceleration(
    speed: npt.ArrayLike,
    power: npt.ArrayLike,
    theta: npt.ArrayLike,
    headwind: npt.ArrayLike,
    physics: params.PhysicsParams,
) -> np.ndarray:
    """Computes dv/dt from the equation of motion.

    This form is singular at zero speed because of the P/v term. The solver
    uses `speed_cubed_rate` instead.

    Args:
        speed: Bike speed [m/s]; must be nonzero.
        power: Rider's pedal power [W]; eta * power reaches the wheel.
        theta: Road incline angle [rad].
        headwind: Wind speed opposing the rider [m/s].
        physics: Physical parameters.

    Returns:
        Acceleration [m/s^2].
    """
    drive = physics.drivetrain_efficiency * power / speed
    resistance = resistive_force(speed, theta, headwind, physics)
    return (drive - resistance) / physics.effective_mass


def speed_cubed_rate(
    speed: npt.ArrayLike,
    power: npt.ArrayLike,
    theta: npt.ArrayLike,
    headwind: npt.ArrayLike,
    physics: params.PhysicsParams,
) -> np.ndarray:
    """Computes d(v^3)/ds, the equation of motion in distance form.

    Since m_eff v^2 dv/ds = eta P - v F_res, the state z = v^3 obeys

        dz/ds = (3 / m_eff) (eta P - v F_res(v)),

    with eta the drivetrain efficiency and m_eff = m + I / r^2 the mass
    including the wheels' rotational inertia.

    which has no singularity at v = 0, so a standing start is well posed.

    Args:
        speed: Bike speed [m/s].
        power: Rider's pedal power [W]; eta * power reaches the wheel.
        theta: Road incline angle [rad].
        headwind: Wind speed opposing the rider [m/s].
        physics: Physical parameters.

    Returns:
        d(v^3)/ds [m^2/s^3].
    """
    resistance = resistive_force(speed, theta, headwind, physics)
    return (
        3.0 / physics.effective_mass
        * (physics.drivetrain_efficiency * power - speed * resistance)
    )


def steady_state_speed(
    power: float,
    theta: float,
    headwind: float,
    physics: params.PhysicsParams,
    max_speed: float = 60.0,
) -> float:
    """Finds the speed at which the forces balance.

    Args:
        power: Constant pedal power [W].
        theta: Constant road incline angle [rad].
        headwind: Constant headwind [m/s].
        physics: Physical parameters.
        max_speed: Upper end of the search bracket [m/s].

    Returns:
        The speed [m/s] at which dv/dt = 0.
    """

    def surplus_power(speed: float) -> float:
        resistance = resistive_force(speed, theta, headwind, physics)
        return physics.drivetrain_efficiency * power - speed * resistance

    return optimize.brentq(surplus_power, 1e-6, max_speed)
