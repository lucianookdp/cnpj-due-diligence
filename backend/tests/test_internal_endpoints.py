from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.core.db import get_db
from app.main import app

PATH = "/api/v1/internal/worker/run-once"


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_rejects_when_no_secret_is_configured(client):
    # Settings() picked up from the real test .env, which never sets
    # worker_trigger_secret — the trigger must be disabled by default, not
    # openly callable with an empty header.
    response = client.post(PATH, headers={"X-Worker-Secret": ""})

    assert response.status_code == 401


def test_rejects_missing_header(client):
    response = client.post(PATH)

    assert response.status_code == 401


def test_rejects_wrong_secret(client):
    app.dependency_overrides[get_settings] = lambda: Settings(worker_trigger_secret="correct")
    try:
        response = client.post(PATH, headers={"X-Worker-Secret": "wrong"})
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 401


def test_runs_one_worker_pass_with_the_correct_secret(client):
    app.dependency_overrides[get_settings] = lambda: Settings(worker_trigger_secret="correct")
    try:
        with patch("app.api.v1.endpoints.internal.run_once", return_value=3) as mock_run_once:
            response = client.post(PATH, headers={"X-Worker-Secret": "correct"})
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 200
    assert response.json() == {"processed": 3}
    mock_run_once.assert_called_once()
