"""Physiological parameters of the rider."""

import dataclasses


@dataclasses.dataclass(frozen=True)
class RiderParams:
    """Parameters of the two-reserve stamina model.

    The rider has a fast, rechargeable reserve above their current critical
    power, and a slow durability reserve that only drains. See
    power_model/README.md for the equations.

    Attributes:
        lt1: First lactate threshold, LT1 [W]. Riding below it causes no
            lasting fatigue, and critical power never falls below it.
        lt2: Second lactate threshold, LT2 [W], taken as the critical power
            of the fresh rider, CP_0.
        w_prime: Work capacity above critical power when fresh, W'_0 [J].
        p_max: Hard cap on instantaneous power [W].
        alpha: Recovery rate coefficient [-].
        beta: Recovery saturation exponent [-].
        fatigue_exponent: How steeply fatigue grows with intensity,
            gamma [-].
        fatigue_time: Fatigue at which critical power has lost 63% of the
            span between LT2 and LT1, tau_F [s]. Fatigue is counted in
            seconds ridden at LT2. Infinity turns the loss of critical
            power off.
        work_capacity: Work done at which W' has fallen to 37% of its
            fresh value, E_W [J]. Infinity turns the loss of W' off.
    """

    lt1: float = 225.0
    lt2: float = 300.0
    w_prime: float = 20_000.0
    p_max: float = 900.0
    alpha: float = 1.0
    beta: float = 1.0
    fatigue_exponent: float = 1.7
    fatigue_time: float = 3000.0
    work_capacity: float = 4.3e6

    def __post_init__(self):
        if not 0 < self.lt1 < self.lt2 <= self.p_max:
            raise ValueError(
                "Need 0 < lt1 < lt2 <= p_max, got "
                f"{self.lt1}, {self.lt2}, {self.p_max}."
            )

    @property
    def cp(self) -> float:
        """Critical power of the fresh rider, CP_0 = LT2 [W]."""
        return self.lt2
