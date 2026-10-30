"""Hard limits shared by the schema, ingestion and service layers."""

from typing import Final

# ICH Q2(R2): linearity should be evaluated with a minimum of 5 concentration levels.
MIN_CONCENTRATION_LEVELS: Final[int] = 5

# Upper bounds protect the service from resource-exhaustion payloads.
MAX_POINTS: Final[int] = 1_000
MAX_UPLOAD_BYTES: Final[int] = 1_000_000  # 1 MB
MAX_INGESTION_ISSUES_REPORTED: Final[int] = 20

DEFAULT_R_SQUARED_LIMIT: Final[float] = 0.999
DEFAULT_CONFIDENCE_LEVEL: Final[float] = 0.95
