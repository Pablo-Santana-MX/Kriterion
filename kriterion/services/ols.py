"""Pure numerical core: Ordinary Least Squares simple linear regression.

No I/O, no framework imports. Everything is deterministic and unit-testable.

Model:            y = b0 + b1 * x + e
Slope:            b1 = Sxy / Sxx
Intercept:        b0 = ybar - b1 * xbar
Determination:    R^2 = 1 - RSS / TSS
Residual SE:      s = sqrt(RSS / (n - 2))
SE(b1):           s / sqrt(Sxx)
SE(b0):           s * sqrt(1/n + xbar^2 / Sxx)
Confidence band:  b +/- t_{1-alpha/2, n-2} * SE(b)

Data are mean-centred before forming Sxx / Sxy. This avoids the catastrophic
cancellation of the textbook ``n*Sum(x^2) - (Sum x)^2`` form, which matters for
chromatographic areas that are large and tightly clustered.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy import stats

from kriterion.core.errors import CalculationError

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class OLSResult:
    """Immutable result of a simple linear OLS fit."""

    n: int
    degrees_of_freedom: int
    slope: float
    intercept: float
    r: float
    r_squared: float
    residual_std_error: float
    slope_se: float
    intercept_se: float
    slope_ci: tuple[float, float]
    intercept_ci: tuple[float, float]
    confidence_level: float
    rss: float
    fitted: FloatArray
    residuals: FloatArray


def _as_vector(values: ArrayLike, name: str) -> FloatArray:
    arr = np.asarray(values, dtype=np.float64)
    if arr.ndim != 1:
        raise CalculationError(f"'{name}' must be a one-dimensional sequence.")
    if not np.isfinite(arr).all():
        raise CalculationError(f"'{name}' contains NaN or infinite values.")
    return arr


def fit_ols(x: ArrayLike, y: ArrayLike, *, confidence_level: float = 0.95) -> OLSResult:
    """Fit ``y = b0 + b1 x`` by ordinary least squares.

    Raises:
        CalculationError: if the regression is undefined (fewer than 3 points,
            no variation in ``x`` or ``y``, mismatched lengths, non-finite data).
    """
    if not 0.0 < confidence_level < 1.0:
        raise CalculationError("confidence_level must be strictly between 0 and 1.")

    xv = _as_vector(x, "concentrations")
    yv = _as_vector(y, "areas")
    if xv.size != yv.size:
        raise CalculationError(
            f"Length mismatch: {xv.size} concentrations vs {yv.size} areas."
        )

    n = int(xv.size)
    if n < 3:
        # With n = 2 the fit is exact and the residual variance has 0 d.o.f.
        raise CalculationError("At least 3 points are required to estimate fit uncertainty.")
    if np.ptp(xv) == 0.0:
        raise CalculationError("All concentrations are identical; the slope is undefined.")

    x_mean = float(xv.mean())
    y_mean = float(yv.mean())
    xc = xv - x_mean
    yc = yv - y_mean

    sxx = float(np.dot(xc, xc))
    sxy = float(np.dot(xc, yc))
    tss = float(np.dot(yc, yc))
    if tss == 0.0:
        raise CalculationError("All peak areas are identical; R² is undefined.")

    slope = sxy / sxx
    intercept = y_mean - slope * x_mean

    fitted = intercept + slope * xv
    residuals = yv - fitted
    rss = float(np.dot(residuals, residuals))

    r_squared = min(1.0, max(0.0, 1.0 - rss / tss))
    r = math.copysign(math.sqrt(r_squared), slope)

    dof = n - 2
    s = math.sqrt(rss / dof)
    slope_se = s / math.sqrt(sxx)
    intercept_se = s * math.sqrt(1.0 / n + (x_mean**2) / sxx)

    t_crit = float(stats.t.ppf(1.0 - (1.0 - confidence_level) / 2.0, dof))
    slope_ci = (slope - t_crit * slope_se, slope + t_crit * slope_se)
    intercept_ci = (intercept - t_crit * intercept_se, intercept + t_crit * intercept_se)

    return OLSResult(
        n=n,
        degrees_of_freedom=dof,
        slope=slope,
        intercept=intercept,
        r=r,
        r_squared=r_squared,
        residual_std_error=s,
        slope_se=slope_se,
        intercept_se=intercept_se,
        slope_ci=slope_ci,
        intercept_ci=intercept_ci,
        confidence_level=confidence_level,
        rss=rss,
        fitted=fitted,
        residuals=residuals,
    )
