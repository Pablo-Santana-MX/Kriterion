"""Domain exceptions.

Each exception carries an HTTP status and a stable machine-readable ``code`` so
that clients (and audit tooling) can branch on the error without parsing text.
"""

from __future__ import annotations

from typing import Any


class KriterionError(Exception):
    """Base class for all expected, client-attributable errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, details: list[str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []

    def to_payload(self, request_id: str | None = None) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
                "request_id": request_id,
            }
        }


class InputValidationError(KriterionError):
    """The submitted data violates a methodological or structural rule."""

    status_code = 422
    code = "invalid_input"


class IngestionError(KriterionError):
    """An uploaded analytical file could not be parsed without ambiguity."""

    status_code = 422
    code = "ingestion_error"


class CalculationError(KriterionError):
    """The regression is mathematically undefined for the given data."""

    status_code = 422
    code = "calculation_error"


class PayloadTooLargeError(KriterionError):
    status_code = 413
    code = "payload_too_large"
