import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_cors_allows_configured_frontend_and_rejects_other_origins(settings):
    with TestClient(create_app(settings)) as client:
        headers = {"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST",
                   "Access-Control-Request-Headers": "content-type"}
        allowed = client.options("/sessions/start", headers=headers)
        assert allowed.status_code == 200
        assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
        denied = client.options("/sessions/start", headers={**headers, "Origin": "https://other.example"})
        assert denied.status_code == 400
        assert "access-control-allow-origin" not in denied.headers


def test_cors_rejects_wildcard():
    with pytest.raises(ValueError, match="origens HTTP"):
        Settings(database_url="sqlite:///:memory:", cors_origins=("*",))
