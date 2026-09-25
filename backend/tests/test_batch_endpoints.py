import pytest
from fastapi.testclient import TestClient

import app.core.rate_limit as rate_limit_module
from app.core.db import get_db
from app.main import app
from app.services import batch_check


@pytest.fixture(autouse=True)
def clear_rate_limit_buckets():
    rate_limit_module._buckets.clear()
    yield


@pytest.fixture
def client(db, monkeypatch):
    # The real background job opens its own session on the dev database;
    # these tests only cover the HTTP contract.
    monkeypatch.setattr(batch_check, "process_batch", lambda *_args, **_kwargs: None)
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def _token(client, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register", json={"email": email, "password": "longenough123"}
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_batch_requires_login(client):
    assert client.post("/api/v1/batches", json={"cnpjs": ["11222333000181"]}).status_code in (
        401,
        403,
    )


def test_batch_rejects_oversized_or_empty_lists(client):
    headers = _token(client, "a@example.com")
    too_many = [f"{i:014d}" for i in range(51)]
    assert (
        client.post("/api/v1/batches", json={"cnpjs": too_many}, headers=headers).status_code == 422
    )
    assert (
        client.post("/api/v1/batches", json={"cnpjs": ["abc"]}, headers=headers).status_code == 422
    )


def test_batch_is_created_and_only_visible_to_its_owner(client):
    owner = _token(client, "owner@example.com")
    created = client.post(
        "/api/v1/batches", json={"cnpjs": ["11.222.333/0001-81", "11222333000181"]}, headers=owner
    )
    assert created.status_code == 202
    batch = created.json()
    assert [i["cnpj"] for i in batch["items"]] == ["11222333000181"]

    assert client.get(f"/api/v1/batches/{batch['id']}", headers=owner).status_code == 200
    stranger = _token(client, "stranger@example.com")
    assert client.get(f"/api/v1/batches/{batch['id']}", headers=stranger).status_code == 404
    assert client.get("/api/v1/batches", headers=stranger).json() == []
