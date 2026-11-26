from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.core.config import Settings
from app.db.session import get_db
from app.main import create_app


@pytest.fixture
def client():
    app = create_app()
    db = Mock()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client, db


def test_liveness_does_not_query_database(client):
    http, db = client
    response = http.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "code": 0,
        "message": "success",
        "data": {"status": "ok", "database": "not_checked"},
    }
    db.execute.assert_not_called()


def test_database_check(client):
    http, db = client
    response = http.get("/api/v1/health?check_database=true")
    assert response.status_code == 200
    assert response.json()["data"]["database"] == "connected"
    db.execute.assert_called_once()


def test_database_failure_does_not_leak_credentials(client):
    http, db = client
    db.execute.side_effect = OperationalError("SELECT 1", {}, Exception("private-password"))
    response = http.get("/api/v1/health?check_database=true")
    assert response.status_code == 503
    assert response.json() == {
        "code": 50301,
        "message": "Database unavailable",
        "data": None,
    }


def test_validation_and_not_found_envelopes(client):
    http, _ = client
    assert http.get("/api/v1/health?check_database=invalid").json()["code"] == 42200
    assert http.get("/missing").json()["code"] == 40400


def test_cors(client):
    http, _ = client
    response = http.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    denied = http.get("/api/v1/health", headers={"Origin": "https://untrusted.invalid"})
    assert "access-control-allow-origin" not in denied.headers


def test_authentication_requires_bearer(client):
    http, _ = client
    assert http.get("/api/v1/users/me").status_code == 401


def test_mysql_password_special_characters():
    settings = Settings(_env_file=None, mysql_password="secret@:/%")
    assert settings.database_url.password == "secret@:/%"
    assert settings.database_url.drivername == "mysql+pymysql"
