"""Fits rider parameters to measured best efforts.

A best effort is the highest power a rider has held for some duration, for
example 426 W for 20 minutes. The model predicts the same quantity with
`cp_model.power_duration_curve`, so parameters are found by making the two
agree. Fitting through the model matters: a critical power read off a plain
CP fit already contains some of the fatigue this model adds separately.

Which parameters a set of efforts can pin down:

    efforts of 3 to 20 min     lt2 and w_prime
    one effort of 1 h or more  fatigue_time
    two such efforts           fatigue_time and fatigue_exponent
"""

import dataclasses
from typing import Sequence

import numpy as np
from scipy import optimize

from power_model import cp_model
from power_model import params

# Fields that may be fitted. Each is searched on a log scale.
FITTABLE = (
    "lt2", "w_prime", "fatigue_time", "fatigue_exponent", "work_capacity"
)


def _with_values(
    rider: params.RiderParams,
    fields: Sequence[str],
    values: Sequence[float],
    lt1_ratio: float | None,
) -> params.RiderParams:
    """Returns the rider with some fields replaced."""
    changes = dict(zip(fields, (float(value) for value in values)))
    if lt1_ratio is not None and "lt2" in changes:
        changes["lt1"] = lt1_ratio * changes["lt2"]
    return dataclasses.replace(rider, **changes)


def fit(
    rider: params.RiderParams,
    efforts: Sequence[tuple[float, float]],
    fields: Sequence[str] = ("lt2", "w_prime"),
    lt1_ratio: float | None = None,
) -> params.RiderParams:
    """Fits some of a rider's parameters to best efforts.

    Minimizes the squared relative error between the model's power-duration
    curve and the efforts, starting from the given rider.

    Args:
        rider: Starting values, and the values of every field not fitted.
        efforts: Best efforts as (duration [s], power [W]) pairs.
        fields: Names of the fields to fit, from `FITTABLE`. There must be
            at least as many efforts as fields.
        lt1_ratio: If given, LT1 is kept at this fraction of LT2 while LT2
            is fitted. Otherwise LT1 stays as it is.

    Returns:
        The rider with the fitted fields replaced.

    Raises:
        ValueError: If a field cannot be fitted or there are too few efforts.
    """
    unknown = sorted(set(fields) - set(FITTABLE))
    if unknown:
        raise ValueError(f"Cannot fit: {', '.join(unknown)}.")
    if len(efforts) < len(fields):
        raise ValueError("Need at least as many efforts as fitted fields.")
    durations = np.array([duration for duration, _ in efforts], float)
    powers = np.array([power for _, power in efforts], float)

    def residuals(log_values: np.ndarray) -> np.ndarray:
        candidate = _with_values(
            rider, fields, np.exp(log_values), lt1_ratio
        )
        curve = cp_model.power_duration_curve(durations, candidate)
        return curve / powers - 1.0

    start = np.log([getattr(rider, field) for field in fields])
    result = optimize.least_squares(
        residuals, start, x_scale=0.05, diff_step=1e-3
    )
    return _with_values(rider, fields, np.exp(result.x), lt1_ratio)


def fit_errors(
    rider: params.RiderParams, efforts: Sequence[tuple[float, float]]
) -> np.ndarray:
    """Computes how far the model is from each best effort.

    Args:
        rider: Rider parameters.
        efforts: Best efforts as (duration [s], power [W]) pairs.

    Returns:
        Model power minus measured power for each effort [W].
    """
    durations = np.array([duration for duration, _ in efforts], float)
    powers = np.array([power for _, power in efforts], float)
    return cp_model.power_duration_curve(durations, rider) - powers
