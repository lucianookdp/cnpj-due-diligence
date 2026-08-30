"""Guards against the app failing to even import — e.g. a module-level import
like WeasyPrint missing its native libs, which no other test would catch
since none of them import app.main.
"""

from fastapi.testclient import TestClient

from app.main import app


def test_health_check():
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
