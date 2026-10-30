"""Runtime configuration for the Kriterion API.

All configuration is read once from environment variables and exposed as an
immutable ``Settings`` object. Nothing here performs I/O beyond ``os.environ``.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache

API_VERSION = "1.1.0"
ENGINE_NAME = "kriterion-ols"

_DEFAULT_ORIGINS: tuple[str, ...] = ("http://localhost:3000",)
_VALID_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


@dataclass(frozen=True, slots=True)
class Settings:
    """Immutable application settings."""

    allowed_origins: tuple[str, ...]
    log_level: str
    environment: str


def _parse_origins(raw: str | None) -> tuple[str, ...]:
    """Parse a comma-separated ``ALLOWED_ORIGINS`` value.

    Wildcards are rejected: the API enables credentialed CORS, and a wildcard
    origin together with credentials is both invalid per the CORS spec and a
    violation of least privilege.
    """
    if not raw:
        return _DEFAULT_ORIGINS
    origins = tuple(o.strip().rstrip("/") for o in raw.split(",") if o.strip())
    if "*" in origins:
        raise ValueError(
            "ALLOWED_ORIGINS must list explicit origins; wildcard '*' is not permitted."
        )
    return origins or _DEFAULT_ORIGINS


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings (cached after first call)."""
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    if level not in _VALID_LOG_LEVELS:
        level = "INFO"
    return Settings(
        allowed_origins=_parse_origins(os.getenv("ALLOWED_ORIGINS")),
        log_level=level,
        environment=os.getenv("KRITERION_ENV", "development"),
    )


def configure_logging(level: str = "INFO") -> None:
    """Configure UTC-stamped logging (ALCOA+ 'Contemporaneous' / 'Consistent')."""
    import time

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    formatter.converter = time.gmtime  # always UTC, independent of host timezone

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
