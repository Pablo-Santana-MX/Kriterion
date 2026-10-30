"""HTTP contract tests. Skipped automatically if FastAPI/httpx are not installed."""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("multipart")

from fastapi.testclient import TestClient  # noqa: E402

from index import create_app  # noqa: E402

client = TestClient(create_app(), raise_server_exceptions=False)
BODY = {
    "concentrations": [10.0, 20.0, 30.0, 40.0, 50.0],
    "areas": [12520.0, 24985.0, 37540.0, 50012.0, 62490.0],
    "r_squared_limit": 0.999,
}


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json()["status"] == "operational"


def test_calculate_ok_and_request_id_echoed():
    r = client.post("/api/v1/linearity/calculate", json=BODY, headers={"X-Request-ID": "abc-12345678"})
    assert r.status_code == 200
    assert r.headers["X-Request-ID"] == "abc-12345678"
    assert r.json()["verdict"] == "PASS"
    assert r.json()["audit"]["request_id"] == "abc-12345678"


def test_unsafe_request_id_replaced():
    r = client.get("/api/health", headers={"X-Request-ID": "bad id\nwith newline"})
    assert r.headers["X-Request-ID"] != "bad id\nwith newline"


def test_schema_error_envelope():
    r = client.post("/api/v1/linearity/calculate", json={"concentrations": [1], "areas": []})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


def test_domain_error_envelope():
    r = client.post("/api/v1/linearity/calculate",
                    json={"concentrations": [1, 2, 3], "areas": [1, 2, 3]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_input"


def test_csv_upload_ok_and_malformed():
    good = "c,a\n" + "\n".join(f"{c},{a}" for c, a in zip(BODY["concentrations"], BODY["areas"]))
    r = client.post("/api/v1/linearity/calculate/csv",
                    files={"file": ("cal.csv", good.encode(), "text/csv")})
    assert r.status_code == 200 and r.json()["audit"]["source_filename"] == "cal.csv"

    r = client.post("/api/v1/linearity/calculate/csv",
                    files={"file": ("bad.csv", b"c,a\n1,2\n3,x\n", "text/csv")})
    assert r.status_code == 422 and r.json()["error"]["code"] == "ingestion_error"


def test_oversize_upload_rejected():
    r = client.post("/api/v1/linearity/calculate/csv",
                    files={"file": ("big.csv", b"1,2\n" * 400_000, "text/csv")})
    assert r.status_code == 413
