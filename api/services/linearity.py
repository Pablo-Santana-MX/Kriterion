"""Linearity orchestration: validation rules, verdict, and audit metadata."""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Sequence
from datetime import datetime, timezone

from api.core.errors import InputValidationError
from api.core.limits import MIN_CONCENTRATION_LEVELS
from api.core.settings import API_VERSION, ENGINE_NAME
from api.schemas.linearity import (
    AuditTrail,
    CoefficientStats,
    Criterion,
    Interval,
    LinearityResponse,
)
from api.services.ingestion import ParsedCalibration
from api.services.ols import OLSResult, fit_ols

logger = logging.getLogger("kriterion_api.linearity")


def _input_fingerprint(conc: Sequence[float], areas: Sequence[float]) -> str:
    """SHA-256 over a canonical JSON form (float repr round-trips exactly)."""
    canonical = json.dumps(
        {"concentrations": list(conc), "areas": list(areas)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _check_design(conc: Sequence[float]) -> None:
    levels = len(set(conc))
    if levels < MIN_CONCENTRATION_LEVELS:
        raise InputValidationError(
            f"ICH Q2(R2) requires at least {MIN_CONCENTRATION_LEVELS} distinct "
            f"concentration levels for linearity; received {levels}."
        )


def _evaluate(fit: OLSResult, r_squared_limit: float) -> list[Criterion]:
    lo, hi = fit.intercept_ci
    return [
        Criterion(
            name="r_squared",
            required=True,
            passed=fit.r_squared >= r_squared_limit,
            observed=fit.r_squared,
            limit=r_squared_limit,
            description="Coefficient of determination must meet the acceptance limit.",
        ),
        Criterion(
            name="intercept_includes_zero",
            required=False,
            passed=lo <= 0.0 <= hi,
            observed=lo <= 0.0 <= hi,
            description=(
                f"{fit.confidence_level:.0%} CI of the y-intercept contains zero "
                "(informational; assess against method-specific criteria)."
            ),
        ),
    ]


def run_linearity(
    concentrations: Sequence[float],
    areas: Sequence[float],
    *,
    r_squared_limit: float,
    confidence_level: float,
    request_id: str,
    source: ParsedCalibration | None = None,
    source_filename: str | None = None,
) -> LinearityResponse:
    _check_design(concentrations)
    fit = fit_ols(concentrations, areas, confidence_level=confidence_level)
    criteria = _evaluate(fit, r_squared_limit)
    compliant = all(c.passed for c in criteria if c.required)
    fingerprint = _input_fingerprint(concentrations, areas)

    logger.info(
        "linearity_calculated request_id=%s n=%d r2=%.8f verdict=%s input_sha256=%s",
        request_id, fit.n, fit.r_squared, "PASS" if compliant else "FAIL", fingerprint,
    )

    return LinearityResponse(
        slope=fit.slope,
        intercept=fit.intercept,
        r_squared=fit.r_squared,
        is_compliant=compliant,
        verdict="PASS" if compliant else "FAIL",
        n_points=fit.n,
        degrees_of_freedom=fit.degrees_of_freedom,
        r=fit.r,
        residual_std_error=fit.residual_std_error,
        confidence_level=fit.confidence_level,
        slope_stats=CoefficientStats(
            estimate=fit.slope,
            std_error=fit.slope_se,
            confidence_interval=Interval(lower=fit.slope_ci[0], upper=fit.slope_ci[1]),
        ),
        intercept_stats=CoefficientStats(
            estimate=fit.intercept,
            std_error=fit.intercept_se,
            confidence_interval=Interval(lower=fit.intercept_ci[0], upper=fit.intercept_ci[1]),
        ),
        fitted=fit.fitted.tolist(),
        residuals=fit.residuals.tolist(),
        criteria=criteria,
        audit=AuditTrail(
            request_id=request_id,
            timestamp_utc=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            engine=ENGINE_NAME,
            engine_version=API_VERSION,
            input_sha256=fingerprint,
            source_filename=source_filename,
            source_file_sha256=source.source_sha256 if source else None,
            ingestion_warnings=list(source.warnings) if source else [],
        ),
    )
