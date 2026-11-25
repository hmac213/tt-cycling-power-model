"""Critical Power / W' stamina model.

B(t) is the remaining anaerobic reserve, with 0 <= B <= W'.

    P > CP:  dB/dt = -(P - CP)                         (expenditure)
    P = CP:  dB/dt = 0                                 (neutral)
    P < CP:  dB/dt = alpha (CP - P) (1 - B/W')^beta    (recovery)

Every function broadcasts over numpy arrays.
"""

import dataclasses

import numpy as np
from numpy import typing as npt

from power_model import params

_MIN_DEFICIT = 1e-12
_MIN_POSITIVE = 1e-300


def reserve_rate(
    power: npt.ArrayLike,
    reserve: npt.ArrayLike,
    rider: params.RiderParams,
) -> np.ndarray:
    """Computes dB/dt.

    Args:
        power: Instantaneous power P [W].
        reserve: Remaining anaerobic reserve B [J].
        rider: Rider parameters.

    Returns:
        Rate of change of the reserve [W].
    """
    power, reserve = np.broadcast_arrays(
        np.asarray(power, float), np.asarray(reserve, float)
    )
    deficit = np.clip(1.0 - reserve / rider.w_prime, 0.0, None)
    recovery = rider.alpha * (rider.cp - power) * deficit**rider.beta
    return np.where(power >= rider.cp, rider.cp - power, recovery)


def step_reserve(
    reserve: npt.ArrayLike,
    power: npt.ArrayLike,
    duration: npt.ArrayLike,
    rider: params.RiderParams,
) -> np.ndarray:
    """Advances B over an interval of constant power, exactly.

    Expenditure is not clamped at B = 0. A negative result means the pacing
    plan is infeasible, which the solver enforces as a constraint.

    For recovery, with x = 1 - B/W' and k = alpha (CP - P) / W', the reserve
    solves dx/dt = -k x^beta, which has a closed form.

    Args:
        reserve: Reserve B at the start of the interval [J].
        power: Constant power P over the interval [W].
        duration: Length of the interval [s].
        rider: Rider parameters.

    Returns:
        Reserve B at the end of the interval [J].
    """
    reserve, power, duration = np.broadcast_arrays(
        np.asarray(reserve, float),
        np.asarray(power, float),
        np.asarray(duration, float),
    )
    spent = reserve - (power - rider.cp) * duration

    deficit = np.clip(1.0 - reserve / rider.w_prime, _MIN_DEFICIT, None)
    rate = rider.alpha * np.clip(rider.cp - power, 0.0, None) / rider.w_prime
    if rider.beta == 1.0:
        new_deficit = deficit * np.exp(-rate * duration)
    else:
        exponent = 1.0 - rider.beta
        floor = 0.0 if exponent > 0 else _MIN_POSITIVE
        base = np.clip(
            deficit**exponent - exponent * rate * duration, floor, None
        )
        new_deficit = base ** (1.0 / exponent)
    recovered = rider.w_prime * (1.0 - new_deficit)

    return np.where(power >= rider.cp, spent, recovered)


def time_to_exhaustion(
    power: npt.ArrayLike,
    rider: params.RiderParams,
) -> np.ndarray:
    """Computes how long a fresh rider can hold a constant power above CP.

    Args:
        power: Constant power P > CP [W].
        rider: Rider parameters.

    Returns:
        Time to exhaustion W' / (P - CP) [s].
    """
    return rider.w_prime / (np.asarray(power, float) - rider.cp)


# CP never falls below this fraction of its fresh value.
_MIN_FATIGUE_FACTOR = 0.5


def fatigue_factor(
    time: npt.ArrayLike,
    rider: params.RiderParams,
) -> np.ndarray:
    """Computes how much of the fresh CP is left after riding for a while.

    CP(t) / CP = 1 - k ln(t / t0) for t > t0, and 1 before that, where k is
    `fatigue_rate` and t0 is `fatigue_onset`. This is the gradual loss of
    sustainable power over long efforts that the plain CP model leaves out.

    Args:
        time: Elapsed race time [s].
        rider: Rider parameters.

    Returns:
        The factor, between 0.5 and 1.
    """
    ratio = np.maximum(np.asarray(time, float), rider.fatigue_onset)
    factor = 1.0 - rider.fatigue_rate * np.log(ratio / rider.fatigue_onset)
    return np.clip(factor, _MIN_FATIGUE_FACTOR, 1.0)


def at_step(rider: params.RiderParams, index: int) -> params.RiderParams:
    """Returns the rider as they are on one grid step.

    Without `cp_scale` this is the rider unchanged. With it, CP is scaled
    by that step's factor, which is how fatigue enters the solver.

    Args:
        rider: Rider parameters.
        index: Grid step.

    Returns:
        Rider parameters with a plain scalar CP.
    """
    if rider.cp_scale is None:
        return rider
    return dataclasses.replace(
        rider, cp=rider.cp * rider.cp_scale[index], cp_scale=None
    )
