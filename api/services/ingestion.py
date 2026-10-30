"""Strict, non-lossy ingestion of chromatographic calibration data from CSV.

Design principle (ALCOA+ 'Accurate' / 'Complete'): a malformed row is never
silently dropped. Any ambiguity aborts the import with line-level diagnostics,
because a quietly discarded calibration point changes the regression.

Supported: UTF-8 (with/without BOM) and Windows-1252; delimiters ``;`` tab ``,``;
decimal comma when the delimiter is not a comma; optional one-line header;
extra columns are ignored with a warning.
Rejected: NaN/Inf, thousands separators, underscores, missing cells.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field

from api.core.errors import IngestionError
from api.core.limits import MAX_INGESTION_ISSUES_REPORTED, MAX_POINTS, MAX_UPLOAD_BYTES

# Deliberately stricter than float(): rejects 'nan', 'inf', '1_000', ' 0x10 '.
_NUMERIC = re.compile(r"^[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")


@dataclass(frozen=True, slots=True)
class ParsedCalibration:
    concentrations: list[float]
    areas: list[float]
    header: tuple[str, str] | None
    delimiter: str
    encoding: str
    rows_read: int
    source_sha256: str
    warnings: list[str] = field(default_factory=list)


def _decode(raw: bytes) -> tuple[str, str]:
    if b"\x00" in raw:
        raise IngestionError("File appears to be binary, not delimited text.")
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise IngestionError("Unsupported text encoding. Export the file as UTF-8.")


def _detect_delimiter(text: str) -> str:
    first = next((ln for ln in text.splitlines() if ln.strip()), "")
    for candidate in (";", "\t", ","):
        if candidate in first:
            return candidate
    raise IngestionError(
        "No delimiter found. Use two columns separated by ',', ';' or a tab."
    )


def _to_float(cell: str, delimiter: str) -> float | None:
    token = cell.strip()
    if delimiter != "," and token.count(",") == 1 and "." not in token:
        token = token.replace(",", ".")  # decimal comma (ES/DE locales)
    return float(token) if _NUMERIC.match(token) else None


def parse_linearity_csv(raw: bytes) -> ParsedCalibration:
    """Parse a two-column (concentration, area) file into validated floats."""
    if not raw.strip():
        raise IngestionError("The uploaded file is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise IngestionError(f"File exceeds the {MAX_UPLOAD_BYTES // 1000} KB limit.")

    text, encoding = _decode(raw)
    delimiter = _detect_delimiter(text)

    concentrations: list[float] = []
    areas: list[float] = []
    header: tuple[str, str] | None = None
    issues: list[str] = []
    warnings: list[str] = []
    first_row = True
    extra_columns_seen = False

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    for row in reader:
        if not any(cell.strip() for cell in row):
            continue  # blank line

        line = reader.line_num
        if len(row) < 2:
            issues.append(f"Line {line}: expected 2 columns, found {len(row)}.")
            first_row = False
            continue
        if len(row) > 2:
            extra_columns_seen = True

        conc = _to_float(row[0], delimiter)
        area = _to_float(row[1], delimiter)

        if first_row:
            first_row = False
            if conc is None and area is None:
                header = (row[0].strip(), row[1].strip())
                continue

        if conc is None or area is None:
            bad = row[0] if conc is None else row[1]
            issues.append(f"Line {line}: non-numeric value {bad.strip()!r}.")
            continue

        concentrations.append(conc)
        areas.append(area)
        if len(concentrations) > MAX_POINTS:
            raise IngestionError(f"More than {MAX_POINTS} data rows; refusing to process.")

    if issues:
        shown = issues[:MAX_INGESTION_ISSUES_REPORTED]
        hidden = len(issues) - len(shown)
        if hidden:
            shown.append(f"... and {hidden} more issue(s).")
        raise IngestionError(
            f"{len(issues)} row(s) could not be parsed; import aborted to preserve "
            "data completeness.",
            details=shown,
        )
    if not concentrations:
        raise IngestionError("No numeric data rows were found.")

    if extra_columns_seen:
        warnings.append("Columns beyond the first two were ignored.")
    if encoding == "cp1252":
        warnings.append("File was not valid UTF-8; decoded as Windows-1252.")

    return ParsedCalibration(
        concentrations=concentrations,
        areas=areas,
        header=header,
        delimiter=delimiter,
        encoding=encoding,
        rows_read=len(concentrations),
        source_sha256=hashlib.sha256(raw).hexdigest(),
        warnings=warnings,
    )
