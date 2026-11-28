"""Two-reserve stamina model: critical power with durability.

The rider carries three numbers through a race.

    x   deficit of the fast reserve, x = 1 - B / W'_eff   (0 full, 1 empty)
    F   fatigue [s], counted in seconds ridden at LT2; it never recovers
    E   mechanical work done so far [J]

F and E set the level and the size of the fast reserve:

    i      = (P - LT1) / (LT2 - LT1)                  intensity
    dF/dt  = max(i, 0)^gamma                          fatigue
    dE/dt  = P                                        work
    CP     = LT1 + (LT2 - LT1) exp(-(F / tau_F)^2)    current critical power
    W'     = W'_0 exp(-E / E_W)                       current capacity

and the fast reserve B = (1 - x) W' is measured against them:

    P >= CP:  dx/dt = (P - CP) / W'                   (expenditure)
    P <  CP:  dx/dt = -alpha (CP - P) x^beta / W'     (recovery)

With tau_F and E_W infinite this is the classic Critical Power model.

Functions that take a `power` or a slow state use plain arithmetic, so they
accept numpy arrays and CasADi expressions alike.
"""

from typing import Any, Callable

import numpy as np
from numpy import typing as npt

from power_model import params

# The positive part in the fatigue law is rounded off over this width of
# intensity, so that the law has smooth derivatives for the optimizer.
_SMOOTHING = 0.01

_MIN_DEFICIT = 1e-12
_MIN_POSITIVE = 1e-300


def intensity(power: Any, rider: params.RiderParams) -> Any:
    """Places a power between the two thresholds.

    Args:
        power: Power P [W].
        rider: Rider parameters.

    Returns:
        (P - LT1) / (LT2 - LT1): 0 at LT1, 1 at LT2, above 1 beyond it.
    """
    return (power - rider.lt1) / (rider.lt2 - rider.lt1)


def fatigue_rate(power: Any, rider: params.RiderParams) -> Any:
    """Computes dF/dt, how fast fatigue builds at a given power.

    The rate is max(i, 0)^gamma, with the corner at i = 0 rounded off. One
    second at LT2 adds one second of fatigue, and riding below LT1 adds
    essentially none.

    Args:
        power: Power P [W].
        rider: Rider parameters.

    Returns:
        Fatigue gained per second [-].
    """
    level = intensity(power, rider)
    positive = 0.5 * (level + (level * level + _SMOOTHING**2) ** 0.5)
    return positive**rider.fatigue_exponent


def durability(
    fatigue: Any,
    rider: params.RiderParams,
    exp: Callable[[Any], Any] = np.exp,
) -> Any:
    """Computes the durability reserve R left at a given fatigue.

    R = exp(-(F / tau_F)^2) is the share of the span between LT1 and LT2
    that the rider's critical power still covers. It starts flat, so a
    short race barely moves it, and then falls faster.

    Args:
        fatigue: Fatigue F [s].
        rider: Rider parameters.
        exp: The exponential to use; pass `casadi.exp` for expressions.

    Returns:
        R, between 0 and 1.
    """
    return exp(-((fatigue * (1.0 / rider.fatigue_time)) ** 2))


def critical_power(
    fatigue: Any,
    rider: params.RiderParams,
    exp: Callable[[Any], Any] = np.exp,
) -> Any:
    """Computes the rider's current critical power.

    Args:
        fatigue: Fatigue F [s].
        rider: Rider parameters.
        exp: The exponential to use; pass `casadi.exp` for expressions.

    Returns:
        CP = LT1 + (LT2 - LT1) R(F) [W].
    """
    span = rider.lt2 - rider.lt1
    return rider.lt1 + span * durability(fatigue, rider, exp)


def reserve_capacity(
    work: Any,
    rider: params.RiderParams,
    exp: Callable[[Any], Any] = np.exp,
) -> Any:
    """Computes the current size of the fast reserve.

    Args:
        work: Mechanical work done so far, E [J].
        rider: Rider parameters.
        exp: The exponential to use; pass `casadi.exp` for expressions.

    Returns:
        W' = W'_0 exp(-E / E_W) [J].
    """
    return rider.w_prime * exp(-work * (1.0 / rider.work_capacity))


def step_deficit(
    deficit: npt.ArrayLike,
    power: npt.ArrayLike,
    duration: npt.ArrayLike,
    cp: npt.ArrayLike,
    capacity: npt.ArrayLike,
    rider: params.RiderParams,
) -> np.ndarray:
    """Advances the deficit x over an interval of constant power, exactly.

    Critical power and capacity are held fixed over the interval. They
    change slowly, so the solver refreshes them once per grid step.

    Expenditure is not clamped at x = 1. A result above 1 means the reserve
    was overdrawn, which the solver rules out as a constraint.

    For recovery, with k = alpha (CP - P) / W', the deficit solves
    dx/dt = -k x^beta, which has a closed form.

    Args:
        deficit: Deficit x at the start of the interval [-].
        power: Constant power P over the interval [W].
        duration: Length of the interval [s].
        cp: Critical power over the interval [W].
        capacity: Size of the reserve W' over the interval [J].
        rider: Rider parameters.

    Returns:
        Deficit x at the end of the interval [-].
    """
    deficit, power, duration, cp, capacity = np.broadcast_arrays(
        np.asarray(deficit, float),
        np.asarray(power, float),
        np.asarray(duration, float),
        np.asarray(cp, float),
        np.asarray(capacity, float),
    )
    spent = deficit + (power - cp) * duration / capacity

    start = np.clip(deficit, _MIN_DEFICIT, None)
    rate = rider.alpha * np.clip(cp - power, 0.0, None) / capacity
    if rider.beta == 1.0:
        recovered = start * np.exp(-rate * duration)
    else:
        exponent = 1.0 - rider.beta
        floor = 0.0 if exponent > 0 else _MIN_POSITIVE
        base = np.clip(
            start**exponent - exponent * rate * duration, floor, None
        )
        recovered = base ** (1.0 / exponent)
    return np.where(power >= cp, spent, recovered)


def step_state(
    deficit: npt.ArrayLike,
    fatigue: npt.ArrayLike,
    work: npt.ArrayLike,
    power: npt.ArrayLike,
    duration: npt.ArrayLike,
    rider: params.RiderParams,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Advances the whole stamina state over an interval of constant power.

    Critical power and capacity are taken from the fatigue and work at the
    start of the interval.

    Args:
        deficit: Deficit x at the start [-].
        fatigue: Fatigue F at the start [s].
        work: Work done E at the start [J].
        power: Constant power P over the interval [W].
        duration: Length of the interval [s].
        rider: Rider parameters.

    Returns:
        Arrays (deficit, fatigue, work) at the end of the interval.
    """
    power = np.asarray(power, float)
    duration = np.asarray(duration, float)
    end_deficit = step_deficit(
        deficit,
        power,
        duration,
        critical_power(fatigue, rider),
        reserve_capacity(work, rider),
        rider,
    )
    end_fatigue = fatigue + fatigue_rate(power, rider) * duration
    end_work = work + power * duration
    return end_deficit, end_fatigue, end_work


def time_to_exhaustion(
    power: npt.ArrayLike,
    rider: params.RiderParams,
    max_time: float = 6 * 3600.0,
    time_step: float = 1.0,
) -> np.ndarray:
    """Computes how long a fresh rider can hold a constant power.

    The stamina state is stepped forward until the fast reserve is empty.
    Unlike the classic model, powers at and somewhat below LT2 also end in
    exhaustion, because critical power sinks towards the power being held.

    Args:
        power: Constant power P [W].
        rider: Rider parameters.
        max_time: Longest effort to consider [s].
        time_step: Time step of the integration [s].

    Returns:
        Time to exhaustion [s]; infinite if the rider lasts `max_time`.
    """
    power = np.asarray(power, float)
    deficit = np.zeros_like(power)
    fatigue = np.zeros_like(power)
    work = np.zeros_like(power)
    exhausted_at = np.full(power.shape, np.inf)
    for i in range(int(np.ceil(max_time / time_step))):
        end_deficit, fatigue, work = step_state(
            deficit, fatigue, work, power, time_step, rider
        )
        crossed = (end_deficit >= 1.0) & np.isinf(exhausted_at)
        if crossed.any():
            # Place the crossing of x = 1 inside the step by interpolation.
            gain = np.where(crossed, end_deficit - deficit, 1.0)
            inside = (1.0 - deficit) / gain
            exhausted_at = np.where(
                crossed, (i + inside) * time_step, exhausted_at
            )
        deficit = end_deficit
        if np.all(np.isfinite(exhausted_at)):
            break
    return exhausted_at


def power_duration_curve(
    durations: npt.ArrayLike,
    rider: params.RiderParams,
    num_levels: int = 600,
) -> np.ndarray:
    """Computes the best constant power a fresh rider can hold for a time.

    This is the model's own power-duration curve, the quantity that best
    efforts measure. It is found by computing the time to exhaustion at
    many powers between LT1 and P_max and inverting that relation.

    Args:
        durations: Effort durations [s].
        rider: Rider parameters.
        num_levels: Number of powers tried.

    Returns:
        Power [W] for each duration, capped at P_max for efforts shorter
        than P_max can be held, and floored at LT1.
    """
    durations = np.atleast_1d(np.asarray(durations, float))
    levels = np.linspace(rider.lt1, rider.p_max, num_levels)
    limit = time_to_exhaustion(levels, rider, max_time=1.05 * durations.max())
    lasting = np.isfinite(limit)
    if not lasting.any():
        return np.full(durations.shape, rider.p_max)
    # Time to exhaustion falls as power rises, so flip both for np.interp.
    return np.interp(
        durations,
        limit[lasting][::-1],
        levels[lasting][::-1],
        left=rider.p_max,
        right=levels[lasting][0],
    )
