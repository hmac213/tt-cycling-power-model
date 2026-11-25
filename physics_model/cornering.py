"""Cornering: how fast the rider may go, given the corners ahead.

There are two layers.

1. `corner_speed_limit` is the grip limit at a point,
   v^2 |kappa| <= mu g cos(theta).
2. `speed_envelope` is the fastest speed at each point from which the rider
   can still slow down in time for every corner ahead. It is found by
   integrating the hardest possible deceleration (brakes, drag, rolling
   resistance, and gravity, with no pedalling) backwards from each corner.
"""

import math

import numpy as np
from numpy import typing as npt

from physics_model import params

# Stand-in for "no limit" on straights [m/s].
MAX_SPEED = 200.0

_MIN_CURVATURE = 1e-12


def corner_speed_limit(
    curvature: npt.ArrayLike,
    theta: npt.ArrayLike,
    physics: params.PhysicsParams,
) -> np.ndarray:
    """Computes the grip-limited cornering speed.

    Args:
        curvature: Horizontal path curvature [1/m]; the sign is ignored.
        theta: Road incline angle [rad].
        physics: Physical parameters.

    Returns:
        The largest speed [m/s] with lateral acceleration v^2 |kappa| within
        mu g cos(theta), capped at `MAX_SPEED`.
    """
    kappa = np.maximum(np.abs(curvature), _MIN_CURVATURE)
    lateral_accel = physics.mu_corner * physics.g * np.cos(theta)
    return np.minimum(np.sqrt(lateral_accel / kappa), MAX_SPEED)


def speed_envelope(
    distance: npt.ArrayLike,
    corner_speed: npt.ArrayLike,
    theta: npt.ArrayLike,
    headwind: npt.ArrayLike,
    physics: params.PhysicsParams,
) -> np.ndarray:
    """Computes the latest-braking speed envelope.

    Marching backwards from the finish,

        V^2(s) = min(v_corner^2(s), V^2(s + ds) + 2 a(s) ds),
        a = brake_decel + F_res(V, s) / m_eff    (floored at 0),

    so V equals the corner limit inside corners and rises ahead of them as
    fast as full braking allows. Riding at or below V everywhere guarantees
    that every corner can be made.

    Args:
        distance: Increasing sample positions along the course [m].
        corner_speed: Grip-limited speed at each sample [m/s].
        theta: Road incline angle at each sample [rad].
        headwind: Headwind at each sample [m/s].
        physics: Physical parameters.

    Returns:
        The envelope speed V [m/s] at each sample.
    """
    distance = np.asarray(distance, float)
    corner_speed_sq = np.asarray(corner_speed, float) ** 2
    headwind = np.asarray(headwind, float)
    sin_theta = np.sin(theta)
    cos_theta = np.cos(theta)
    aero_coeff = 0.5 * physics.rho * physics.cda
    weight = physics.mass * physics.g

    speed_sq = np.empty_like(corner_speed_sq)
    speed_sq[-1] = corner_speed_sq[-1]
    for i in range(distance.size - 2, -1, -1):
        air_speed = math.sqrt(speed_sq[i + 1]) + headwind[i]
        resistance = aero_coeff * air_speed * abs(air_speed) + weight * (
            physics.crr * cos_theta[i] + sin_theta[i]
        )
        decel = max(
            physics.brake_decel + resistance / physics.effective_mass, 0.0
        )
        step = distance[i + 1] - distance[i]
        speed_sq[i] = min(
            corner_speed_sq[i], speed_sq[i + 1] + 2.0 * decel * step
        )
    return np.sqrt(speed_sq)
