"""Kriterion API entrypoint.

Run locally:  uvicorn index:app --reload --port 8000
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.core.errors import KriterionError
from api.core.middleware import REQUEST_ID_HEADER, RequestIDMiddleware, get_request_id
from api.core.settings import API_VERSION, configure_logging, get_settings
from api.routers import linearity_router

logger = logging.getLogger("kriterion_api")


def create_app() -> FastAPI:
    """Application factory (clean instantiation for integration tests)."""
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="Kriterion HPLC API | S-labs",
        description="Enterprise statistical engine for chromatographic method validation.",
        version=API_VERSION,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    # Added first => inner; CORS added last => outermost, so CORS headers
    # are present even on error responses.
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )

    @app.exception_handler(KriterionError)
    async def _domain_error(request: Request, exc: KriterionError) -> JSONResponse:
        rid = get_request_id(request)
        logger.warning("domain_error request_id=%s code=%s msg=%s", rid, exc.code, exc.message)
        return JSONResponse(exc.to_payload(rid), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _schema_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        rid = get_request_id(request)
        details = [
            f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
        ]
        logger.warning("schema_error request_id=%s n_errors=%d", rid, len(details))
        payload = {
            "error": {
                "code": "invalid_request",
                "message": "The request body failed validation.",
                "details": details,
                "request_id": rid,
            }
        }
        return JSONResponse(payload, status_code=422)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        rid = get_request_id(request)
        logger.exception("unhandled_error request_id=%s", rid)
        payload = {
            "error": {
                "code": "internal_error",
                "message": "An unexpected error occurred.",
                "details": [],
                "request_id": rid,
            }
        }
        return JSONResponse(payload, status_code=500)

    app.include_router(linearity_router.router)

    @app.get("/api/health", tags=["Health"])
    def health_check() -> dict[str, str]:
        """Liveness probe for CI/CD and orchestrators."""
        return {
            "status": "operational",
            "service": "Kriterion HPLC Core Engine",
            "version": API_VERSION,
        }

    return app


app = create_app()
