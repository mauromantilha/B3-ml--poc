from __future__ import annotations

from fastapi.testclient import TestClient

from b3_quant_platform.api.main import app


def test_healthcheck_returns_ok() -> None:
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
