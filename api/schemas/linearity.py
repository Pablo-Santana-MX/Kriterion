"""Pydantic v2 request/response contracts for the linearity endpoints."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.core.limits import (
    DEFAULT_CONFIDENCE_LEVEL,
    DEFAULT_R_SQUARED_LIMIT,
    MAX_POINTS,
)

FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]


class LinearityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concentrations: list[FiniteFloat] = Field(
        ..., min_length=1, max_length=MAX_POINTS, description="Nominal concentrations (e.g. µg/mL)."
    )
    areas: list[FiniteFloat] = Field(
        ..., min_length=1, max_length=MAX_POINTS, description="Detector peak areas, same order."
    )
    r_squared_limit: float = Field(DEFAULT_R_SQUARED_LIMIT, gt=0.0, le=1.0)
    confidence_level: float = Field(DEFAULT_CONFIDENCE_LEVEL, gt=0.0, lt=1.0)

    @model_validator(mode="after")
    def _paired(self) -> "LinearityRequest":
        if len(self.concentrations) != len(self.areas):
            raise ValueError(
                f"'concentrations' ({len(self.concentrations)}) and 'areas' "
                f"({len(self.areas)}) must have the same length."
            )
        return self


class Interval(BaseModel):
    lower: float
    upper: float


class CoefficientStats(BaseModel):
    estimate: float
    std_error: float
    confidence_interval: Interval


class Criterion(BaseModel):
    name: str
    required: bool
    passed: bool
    observed: float | bool
    limit: float | None = None
    description: str


class AuditTrail(BaseModel):
    request_id: str
    timestamp_utc: str
    engine: str
    engine_version: str
    input_sha256: str = Field(description="SHA-256 of the canonical numeric inputs.")
    source_filename: str | None = None
    source_file_sha256: str | None = None
    ingestion_warnings: list[str] = Field(default_factory=list)


class LinearityResponse(BaseModel):
    # Flat fields retained for client compatibility.
    slope: float
    intercept: float
    r_squared: float
    is_compliant: bool
    verdict: Literal["PASS", "FAIL"]

    n_points: int
    degrees_of_freedom: int
    r: float
    residual_std_error: float
    confidence_level: float
    slope_stats: CoefficientStats
    intercept_stats: CoefficientStats
    fitted: list[float]
    residuals: list[float]
    criteria: list[Criterion]
    audit: AuditTrail
