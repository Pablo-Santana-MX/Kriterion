"""OLS core: cross-validated against SciPy and closed-form cases."""

import numpy as np
import pytest
from scipy import stats

from api.core.errors import CalculationError
from api.services.ols import fit_ols

CONC = [10.0, 20.0, 30.0, 40.0, 50.0]
AREAS = [12520.0, 24985.0, 37540.0, 50012.0, 62490.0]


def test_matches_scipy_linregress():
    fit = fit_ols(CONC, AREAS)
    ref = stats.linregress(CONC, AREAS)
    assert fit.slope == pytest.approx(ref.slope, rel=1e-12)
    assert fit.intercept == pytest.approx(ref.intercept, rel=1e-9)
    assert fit.r == pytest.approx(ref.rvalue, rel=1e-12)
    assert fit.r_squared == pytest.approx(ref.rvalue**2, rel=1e-12)
    assert fit.slope_se == pytest.approx(ref.stderr, rel=1e-9)
    assert fit.intercept_se == pytest.approx(ref.intercept_stderr, rel=1e-9)


def test_confidence_intervals_match_scipy():
    fit = fit_ols(CONC, AREAS, confidence_level=0.95)
    ref = stats.linregress(CONC, AREAS)
    t = stats.t.ppf(0.975, 3)
    assert fit.slope_ci[0] == pytest.approx(ref.slope - t * ref.stderr, rel=1e-9)
    assert fit.slope_ci[1] == pytest.approx(ref.slope + t * ref.stderr, rel=1e-9)


def test_perfect_line_recovered_exactly():
    x = np.arange(1.0, 8.0)
    fit = fit_ols(x, 3.0 * x + 2.0)
    assert fit.slope == pytest.approx(3.0)
    assert fit.intercept == pytest.approx(2.0)
    assert fit.r_squared == pytest.approx(1.0)
    assert fit.residual_std_error == pytest.approx(0.0, abs=1e-9)


def test_negative_slope_gives_negative_r():
    fit = fit_ols([1, 2, 3, 4, 5], [10, 8.1, 5.9, 4.2, 1.9])
    assert fit.slope < 0 and fit.r < 0
    assert fit.r**2 == pytest.approx(fit.r_squared)


def test_stable_with_large_offsets():
    """Mean-centering must survive large, tightly clustered values."""
    x = np.array([1e6 + i for i in range(5)], dtype=float)
    y = 2.0 * x + 1e9
    fit = fit_ols(x, y)
    assert fit.slope == pytest.approx(2.0, rel=1e-9)


def test_residuals_sum_to_zero():
    fit = fit_ols(CONC, AREAS)
    assert fit.residuals.sum() == pytest.approx(0.0, abs=1e-8)


@pytest.mark.parametrize(
    "x,y",
    [
        ([1, 2], [1, 2]),  # too few points
        ([1, 1, 1, 1], [1, 2, 3, 4]),  # no x variation
        ([1, 2, 3, 4], [5, 5, 5, 5]),  # no y variation
        ([1, 2, 3], [1, 2]),  # length mismatch
        ([1, 2, float("nan")], [1, 2, 3]),  # non-finite
    ],
)
def test_undefined_cases_raise(x, y):
    with pytest.raises(CalculationError):
        fit_ols(x, y)


def test_bad_confidence_level():
    with pytest.raises(CalculationError):
        fit_ols(CONC, AREAS, confidence_level=1.0)
