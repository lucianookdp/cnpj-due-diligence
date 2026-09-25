import gzip

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.db import get_db
from app.main import app

SECRET = "test-worker-secret"


@pytest.fixture
def client(db, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "worker_trigger_secret", SECRET)
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _payload(rows: int) -> bytes:
    lines = ["# 2026_trimestre_02", "cnpj_root,amount_cents,inscriptions,judicial"]
    lines += [f"{i:08d},{2_000_000 + i},2,0" for i in range(rows)]
    return gzip.compress("\n".join(lines).encode())


def test_pgfn_routes_require_the_worker_secret(client):
    assert client.get("/api/v1/internal/pgfn/status").status_code == 401
    wrong = {"X-Worker-Secret": "nope"}
    assert (
        client.post(
            "/api/v1/internal/pgfn/import", content=_payload(1500), headers=wrong
        ).status_code
        == 401
    )


def test_pgfn_import_then_status(client):
    headers = {"X-Worker-Secret": SECRET}
    response = client.post("/api/v1/internal/pgfn/import", content=_payload(1500), headers=headers)
    assert response.status_code == 200
    assert response.json() == {"reference": "2026_trimestre_02", "companies": 1500}
    assert client.get("/api/v1/internal/pgfn/status", headers=headers).json() == {
        "reference": "2026_trimestre_02",
        "companies": 1500,
    }


def test_pgfn_import_refuses_a_truncated_summary(client):
    response = client.post(
        "/api/v1/internal/pgfn/import", content=_payload(10), headers={"X-Worker-Secret": SECRET}
    )
    assert response.status_code == 422
