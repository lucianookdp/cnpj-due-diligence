import uuid

import pytest
from fastapi.testclient import TestClient

import app.core.rate_limit as rate_limit_module
from app.core.db import get_db
from app.main import app

# A too-short CNPJ fails validation inside the endpoint body, after every
# dependency (including the rate limiter) has already run — so it's a cheap
# way to trip the limit without touching a real provider or the database.
_INVALID_CNPJ = "123"


@pytest.fixture(autouse=True)
def clear_rate_limit_buckets():
    rate_limit_module._buckets.clear()
    yield


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_token(client):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "watchlist-user@example.com", "password": "longenough123"},
    )
    return response.json()["access_token"]


def _hit(client, method, path, times, **kwargs):
    last = None
    for _ in range(times):
        last = getattr(client, method)(path, **kwargs)
    return last


def test_company_dossier_is_rate_limited(client):
    path = f"/api/v1/companies/{_INVALID_CNPJ}"
    _hit(client, "get", path, 30)

    response = client.get(path)

    assert response.status_code == 429


def test_company_pdf_has_a_tighter_limit(client):
    path = f"/api/v1/companies/{_INVALID_CNPJ}/pdf"
    _hit(client, "get", path, 10)

    response = client.get(path)

    assert response.status_code == 429


def test_graph_read_is_rate_limited(client):
    path = f"/api/v1/graph/{_INVALID_CNPJ}"
    _hit(client, "get", path, 15)

    response = client.get(path)

    assert response.status_code == 429


def test_graph_expand_company_is_rate_limited(client):
    path = f"/api/v1/graph/expand/company/{uuid.uuid4()}"
    _hit(client, "post", path, 30)

    response = client.post(path)

    assert response.status_code == 429


def test_graph_expand_person_is_rate_limited(client):
    path = f"/api/v1/graph/expand/person/{uuid.uuid4()}"
    _hit(client, "post", path, 30)

    response = client.post(path)

    assert response.status_code == 429


def test_watchlist_add_is_rate_limited(client, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    body = {"cnpj": _INVALID_CNPJ, "label": None}
    _hit(client, "post", "/api/v1/watchlist", 30, json=body, headers=headers)

    response = client.post("/api/v1/watchlist", json=body, headers=headers)

    assert response.status_code == 429
