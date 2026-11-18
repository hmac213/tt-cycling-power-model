"""Physical parameters of the rider, bike, and environment."""

import dataclasses


@dataclasses.dataclass(frozen=True)
class PhysicsParams:
    """Constants of the equation of motion and the cornering model.

    Attributes:
        mass: Combined mass of rider and bike, m [kg].
        g: Gravitational acceleration [m/s^2].
        rho: Air density [kg/m^3].
        cda: Drag area C_d A [m^2].
        crr: Rolling resistance coefficient C_rr [-].
        mu_corner: Usable lateral grip, i.e. the largest cornering
            acceleration as a fraction of g [-].
        brake_decel: Largest deceleration from the brakes alone [m/s^2].
    """

    mass: float = 80.0
    g: float = 9.81
    rho: float = 1.225
    cda: float = 0.30
    crr: float = 0.004
    mu_corner: float = 0.5
    brake_decel: float = 3.0
