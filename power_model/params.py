"""Physiological parameters of the rider."""

import dataclasses


@dataclasses.dataclass(frozen=True)
class RiderParams:
    """Parameters of the Critical Power / W' model.

    Attributes:
        cp: Critical power CP, the sustainable aerobic threshold [W].
        w_prime: Anaerobic work capacity above CP, W' [J].
        p_max: Hard cap on instantaneous power [W].
        alpha: Recovery rate coefficient [-].
        beta: Recovery saturation exponent [-].
        fatigue_rate: How fast CP declines once the race is long, k [-].
            CP(t) = CP (1 - k ln(t / t0)) for t > t0. Zero turns fatigue off.
        fatigue_onset: Elapsed time t0 after which CP starts to decline [s].
        cp_scale: Per-step multipliers on CP, one per grid step, or None.
            The solver fills this in from the fatigue law; leave it unset.
    """

    cp: float = 300.0
    w_prime: float = 20_000.0
    p_max: float = 900.0
    alpha: float = 1.0
    beta: float = 1.0
    fatigue_rate: float = 0.0
    fatigue_onset: float = 1800.0
    cp_scale: tuple[float, ...] | None = None
