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
        drivetrain_efficiency: Share of the rider's pedal power that reaches
            the rear wheel, eta [-]. 0.977 (a 2.3% chain loss) follows
            Martin et al. (1998), J. Appl. Biomech. 14(3):276-291.
        wheel_inertia: Moment of inertia of both wheels together, I
            [kg m^2]. 0.14 follows Martin et al. (1998).
        wheel_radius: Outside radius of the tyre, r [m]. 0.311 follows
            Martin et al. (1998).
    """

    mass: float = 80.0
    g: float = 9.81
    rho: float = 1.225
    cda: float = 0.30
    crr: float = 0.004
    mu_corner: float = 0.5
    brake_decel: float = 3.0
    drivetrain_efficiency: float = 0.977
    wheel_inertia: float = 0.14
    wheel_radius: float = 0.311

    @property
    def effective_mass(self) -> float:
        """Mass that resists speed changes, m + I / r^2 [kg].

        Spinning the wheels up stores kinetic energy (1/2) I omega^2 with
        omega = v / r, which acts like extra mass I / r^2 in m dv/dt only.
        Gravity and rolling resistance still use the real mass m.
        """
        return self.mass + self.wheel_inertia / self.wheel_radius**2
