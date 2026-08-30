from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import app.core.rate_limit as rate_limit_module
from app.core.db import get_db
from app.main import app


@pytest.fixture(autouse=True)
def clear_rate_limit_buckets():
    # Starlette's TestClient always reports the same fake client host, so
    # every test hitting a rate-limited endpoint shares one bucket unless
    # reset between tests.
    rate_limit_module._buckets.clear()
    yield


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_register_rejects_short_password(client):
    response = client.post(
        "/api/v1/auth/register", json={"email": "a@example.com", "password": "short"}
    )

    assert response.status_code == 422


def test_register_accepts_valid_password(client):
    response = client.post(
        "/api/v1/auth/register", json={"email": "a@example.com", "password": "longenough123"}
    )

    assert response.status_code == 201
    assert "access_token" in response.json()


def test_login_rejects_wrong_password(client):
    client.post(
        "/api/v1/auth/register", json={"email": "a@example.com", "password": "correcthorse"}
    )

    response = client.post(
        "/api/v1/auth/login", json={"email": "a@example.com", "password": "wrongpassword"}
    )

    assert response.status_code == 401


def test_login_is_rate_limited_after_too_many_attempts(client):
    for _ in range(10):
        client.post("/api/v1/auth/login", json={"email": "x@example.com", "password": "whatever"})

    response = client.post(
        "/api/v1/auth/login", json={"email": "x@example.com", "password": "whatever"}
    )

    assert response.status_code == 429


def test_unhandled_error_returns_generic_message_without_leaking_details(db):
    app.dependency_overrides[get_db] = lambda: db
    no_raise_client = TestClient(app, raise_server_exceptions=False)

    try:
        with patch(
            "app.api.v1.endpoints.auth.user_repository.get_by_email",
            side_effect=RuntimeError("db connection string: postgresql://secret"),
        ):
            response = no_raise_client.post(
                "/api/v1/auth/login", json={"email": "a@example.com", "password": "whatever"}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json() == {"detail": "Erro interno do servidor"}
    assert "secret" not in response.text
