"""Service + schema layer (no web framework needed)."""

import pytest
from pydantic import ValidationError

from api.core.errors import InputValidationError
from api.schemas.linearity import LinearityRequest
from api.services.ingestion import parse_linearity_csv
from api.services.linearity import run_linearity

CONC = [10.0, 20.0, 30.0, 40.0, 50.0]
AREAS = [12520.0, 24985.0, 37540.0, 50012.0, 62490.0]
KW = {"r_squared_limit": 0.999, "confidence_level": 0.95, "request_id": "test-request-0001"}


def test_passes_for_reference_data_and_is_computed_not_hardcoded():
    res = run_linearity(CONC, AREAS, **KW)
    assert res.verdict == "PASS" and res.is_compliant
    assert res.n_points == 5 and res.degrees_of_freedom == 3
    assert res.slope == pytest.approx(1249.67, abs=0.5)


def test_poor_data_fails_verdict():
    res = run_linearity(CONC, [12520, 30000, 31000, 52000, 60000], **KW)
    assert res.verdict == "FAIL" and not res.is_compliant


def test_verdict_depends_on_limit():
    strict = run_linearity(CONC, AREAS, **{**KW, "r_squared_limit": 1.0})
    assert strict.verdict == "FAIL"


def test_fingerprint_deterministic_and_sensitive():
    a = run_linearity(CONC, AREAS, **KW).audit.input_sha256
    b = run_linearity(CONC, AREAS, **KW).audit.input_sha256
    changed = run_linearity(CONC, [*AREAS[:-1], AREAS[-1] + 1e-9], **KW).audit.input_sha256
    assert a == b != changed


def test_fewer_than_five_levels_rejected():
    with pytest.raises(InputValidationError):
        run_linearity([1, 2, 3, 4], [1, 2, 3, 4.1], **KW)


def test_replicates_do_not_count_as_levels():
    with pytest.raises(InputValidationError):
        run_linearity([1, 1, 2, 2, 3, 3], [1, 1.1, 2, 2.1, 3, 3.1], **KW)


def test_csv_provenance_recorded():
    parsed = parse_linearity_csv(b"c,a\n" + "\n".join(f"{c},{a}" for c, a in zip(CONC, AREAS)).encode())
    res = run_linearity(parsed.concentrations, parsed.areas, source=parsed,
                        source_filename="cal.csv", **KW)
    assert res.audit.source_file_sha256 == parsed.source_sha256
    assert res.audit.source_filename == "cal.csv"


def test_schema_rejects_mismatch_nan_extra_and_bad_limit():
    with pytest.raises(ValidationError):
        LinearityRequest(concentrations=[1, 2, 3], areas=[1, 2])
    with pytest.raises(ValidationError):
        LinearityRequest(concentrations=[1, 2, float("nan")], areas=[1, 2, 3])
    with pytest.raises(ValidationError):
        LinearityRequest(concentrations=[1], areas=[1], bogus=1)
    with pytest.raises(ValidationError):
        LinearityRequest(concentrations=[1], areas=[1], r_squared_limit=1.5)
