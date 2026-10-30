"""HTTP routes for linearity validation."""

from __future__ import annotations

import os

from fastapi import APIRouter, File, Form, Request, UploadFile

from api.core.errors import PayloadTooLargeError
from api.core.limits import DEFAULT_CONFIDENCE_LEVEL, DEFAULT_R_SQUARED_LIMIT, MAX_UPLOAD_BYTES
from api.core.middleware import get_request_id
from api.schemas.linearity import LinearityRequest, LinearityResponse
from api.services.ingestion import parse_linearity_csv
from api.services.linearity import run_linearity

router = APIRouter(prefix="/api/v1/linearity", tags=["Linearity"])


@router.post("/calculate", response_model=LinearityResponse, summary="Linearity from JSON")
def calculate_linearity(payload: LinearityRequest, request: Request) -> LinearityResponse:
    """OLS linearity assessment of (concentration, area) pairs."""
    return run_linearity(
        payload.concentrations,
        payload.areas,
        r_squared_limit=payload.r_squared_limit,
        confidence_level=payload.confidence_level,
        request_id=get_request_id(request),
    )


@router.post(
    "/calculate/csv", response_model=LinearityResponse, summary="Linearity from a CSV upload"
)
async def calculate_linearity_csv(
    request: Request,
    file: UploadFile = File(..., description="Two columns: concentration, area."),
    r_squared_limit: float = Form(DEFAULT_R_SQUARED_LIMIT, gt=0.0, le=1.0),
    confidence_level: float = Form(DEFAULT_CONFIDENCE_LEVEL, gt=0.0, lt=1.0),
) -> LinearityResponse:
    """Strict CSV ingestion followed by the same engine as the JSON route."""
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise PayloadTooLargeError(f"File exceeds the {MAX_UPLOAD_BYTES // 1000} KB limit.")

    parsed = parse_linearity_csv(raw)
    filename = os.path.basename(file.filename or "")[:255] or None
    return run_linearity(
        parsed.concentrations,
        parsed.areas,
        r_squared_limit=r_squared_limit,
        confidence_level=confidence_level,
        request_id=get_request_id(request),
        source=parsed,
        source_filename=filename,
    )
