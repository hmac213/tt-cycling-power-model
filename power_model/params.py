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
    """

    cp: float = 300.0
    w_prime: float = 20_000.0
    p_max: float = 900.0
    alpha: float = 1.0
    beta: float = 1.0
