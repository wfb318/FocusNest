import os
from datetime import timedelta
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.security import hash_refresh_token, password_hasher
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import AuthSession, User
from app.models.user import utcnow

COOKIE = "focusnest_refresh"
PASSWORD = "Test-only-password-938!"


@pytest.fixture
def context(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "jwt_secret", SecretStr("test-signing-secret-" * 4))
    monkeypatch.setattr(settings, "cookie_secure", False)
    use_mysql = os.environ.get("FOCUSNEST_TEST_MYSQL") == "1"
    if use_mysql:
        engine = create_engine(settings.database_url)
    else:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )

        @event.listens_for(engine, "connect")
        def sqlite_connect(connection, record):
            connection.isolation_level = None
            connection.execute("PRAGMA foreign_keys=ON")

        @event.listens_for(engine, "begin")
        def sqlite_begin(connection):
            connection.exec_driver_sql("BEGIN")

        Base.metadata.create_all(engine)
    with engine.connect() as connection:
        transaction = connection.begin()

        def db_dependency():
            with Session(
                bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
            ) as db:
                yield db

        app = create_app()
        app.dependency_overrides[get_db] = db_dependency
        try:
            with TestClient(app) as client:
                yield client, connection
        finally:
            transaction.rollback()
    engine.dispose()


def registration(client, username=None):
    name = username or "u_" + uuid4().hex[:16]
    payload = {"username": name, "email": name + "@example.com", "password": PASSWORD}
    result = client.post("/api/v1/auth/register", json=payload)
    assert result.status_code == 201, result.text
    return payload, result.json()["data"]


def login(client, payload):
    result = client.post(
        "/api/v1/auth/login",
        json={"username": payload["username"], "password": payload["password"]},
    )
    assert result.status_code == 200, result.text
    return result


def bearer(response):
    return {"Authorization": "Bearer " + response.json()["data"]["access_token"]}


def test_registration_hashes_password_and_excludes_private_fields(context):
    client, connection = context
    payload, user = registration(client)
    stored = connection.execute(
        select(User.password_hash).where(User.id == user["id"])
    ).scalar_one()
    assert stored.startswith("$argon2id$") and stored != PASSWORD
    assert password_hasher.verify(PASSWORD, stored)
    assert "password_hash" not in user and "password" not in user
    assert user["created_at"].endswith("+00:00")


def test_duplicate_username_and_email_normalization(context):
    client, _ = context
    payload, _ = registration(client)
    duplicate_name = {
        **payload,
        "username": payload["username"].upper(),
        "email": "other@example.com",
    }
    assert client.post("/api/v1/auth/register", json=duplicate_name).status_code == 409
    duplicate_email = {
        **payload,
        "username": "u_" + uuid4().hex[:16],
        "email": payload["email"].upper(),
    }
    assert client.post("/api/v1/auth/register", json=duplicate_email).status_code == 409


def test_username_preserves_case_through_registration_login_and_refresh(context):
    client, connection = context
    name = "FocusNest_" + uuid4().hex[:12]
    payload, account = registration(client, name)
    assert account["username"] == name
    assert account["email"] == payload["email"].lower()
    assert connection.execute(
        select(User.username).where(User.id == account["id"])
    ).scalar_one() == name
    for identity in (name.lower(), name.upper(), name.swapcase(), payload["email"].upper()):
        response = login(client, {**payload, "username": identity})
        assert response.json()["data"]["user"]["username"] == name
        profile = client.get("/api/v1/users/me", headers=bearer(response))
        assert profile.json()["data"]["username"] == name
    refreshed = client.post("/api/v1/auth/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["data"]["user"]["username"] == name
    for duplicate in (name.lower(), name.upper()):
        response = client.post(
            "/api/v1/auth/register",
            json={**payload, "username": duplicate, "email": uuid4().hex + "@example.com"},
        )
        assert response.status_code == 409
    wrong_case_password = client.post(
        "/api/v1/auth/login", json={"username": name, "password": PASSWORD.swapcase()}
    )
    assert wrong_case_password.status_code == 401


@pytest.mark.parametrize(
    "changes",
    [
        {"username": "ab"},
        {"username": "invalid space"},
        {"password": "short"},
        {"password": "x" * 129},
        {"email": "invalid"},
        {"is_admin": True},
    ],
)
def test_invalid_registration(context, changes):
    client, _ = context
    payload = {
        "username": "valid_user",
        "email": "valid@example.com",
        "password": PASSWORD,
        **changes,
    }
    result = client.post("/api/v1/auth/register", json=payload)
    assert result.status_code == 422
    assert PASSWORD not in result.text


def test_login_by_email_cookie_flags_and_current_user(context):
    client, _ = context
    payload, user = registration(client)
    result = login(client, {**payload, "username": payload["email"].upper()})
    cookie = result.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api/v1/auth" in cookie
    assert result.headers["cache-control"] == "no-store"
    assert "refresh_token" not in result.json()["data"]
    me = client.get("/api/v1/users/me", headers=bearer(result))
    assert me.status_code == 200 and me.json()["data"]["id"] == user["id"]


def test_wrong_password_and_unknown_user_have_same_error(context):
    client, _ = context
    payload, _ = registration(client)
    wrong = client.post(
        "/api/v1/auth/login", json={"username": payload["username"], "password": "wrong"}
    )
    missing = client.post(
        "/api/v1/auth/login", json={"username": "missing_user", "password": "wrong"}
    )
    assert wrong.status_code == missing.status_code == 401
    assert wrong.json() == missing.json()


def test_profile_isolation_and_protected_fields(context):
    client, _ = context
    alice, alice_user = registration(client)
    bob, bob_user = registration(client)
    alice_token = bearer(login(client, alice))
    bob_token = bearer(login(client, bob))
    updated = client.patch(
        "/api/v1/users/me", json={"nickname": "Alice", "timezone": "UTC"}, headers=alice_token
    )
    assert updated.status_code == 200 and updated.json()["data"]["id"] == alice_user["id"]
    bob_me = client.get("/api/v1/users/me", headers=bob_token).json()["data"]
    assert bob_me["id"] == bob_user["id"] and bob_me["nickname"] is None
    assert (
        client.patch(
            "/api/v1/users/me", json={"id": bob_user["id"]}, headers=alice_token
        ).status_code
        == 422
    )
    assert (
        client.patch(
            "/api/v1/users/me", json={"password_hash": "fake"}, headers=alice_token
        ).status_code
        == 422
    )
    assert client.get("/api/v1/users/" + bob_user["id"], headers=alice_token).status_code == 404
    assert client.get("/api/v1/users/me").status_code == 401


@pytest.mark.parametrize(
    "changes",
    [{"timezone": "Mars/City"}, {"timezone": None}, {"avatar_url": "javascript:alert(1)"}],
)
def test_invalid_profile(context, changes):
    client, _ = context
    payload, _ = registration(client)
    assert (
        client.patch(
            "/api/v1/users/me", json=changes, headers=bearer(login(client, payload))
        ).status_code
        == 422
    )


def test_partial_update_and_clear_optional_fields(context):
    client, _ = context
    payload, _ = registration(client)
    headers = bearer(login(client, payload))
    client.patch("/api/v1/users/me", json={"nickname": "Name", "timezone": "UTC"}, headers=headers)
    result = client.patch("/api/v1/users/me", json={"nickname": None}, headers=headers).json()[
        "data"
    ]
    assert result["nickname"] is None and result["timezone"] == "UTC"


def test_refresh_rotation_hash_storage_and_replay_rejection(context):
    client, connection = context
    payload, _ = registration(client)
    login(client, payload)
    old = client.cookies.get(COOKIE)
    result = client.post("/api/v1/auth/refresh")
    assert result.status_code == 200
    replacement = client.cookies.get(COOKIE)
    assert old != replacement
    stored = connection.execute(select(AuthSession.refresh_token_hash)).scalars().all()
    assert hash_refresh_token(replacement) in stored and replacement not in stored
    client.cookies.clear()
    assert (
        client.post("/api/v1/auth/refresh", headers={"Cookie": COOKIE + "=" + old}).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/refresh", headers={"Cookie": COOKIE + "=" + replacement}
        ).status_code
        == 200
    )


def test_logout_revokes_access_and_refresh(context):
    client, _ = context
    payload, _ = registration(client)
    token = bearer(login(client, payload))
    old = client.cookies.get(COOKIE)
    result = client.post("/api/v1/auth/logout")
    assert result.status_code == 200
    assert client.cookies.get(COOKIE) is None
    assert client.get("/api/v1/users/me", headers=token).status_code == 401
    assert (
        client.post("/api/v1/auth/refresh", headers={"Cookie": COOKIE + "=" + old}).status_code
        == 401
    )


@pytest.mark.parametrize(
    "mutation",
    ["expired", "wrong_type", "wrong_issuer", "missing_exp", "bad_signature", "wrong_user"],
)
def test_invalid_jwt(context, mutation):
    client, _ = context
    payload, _ = registration(client)
    token = login(client, payload).json()["data"]["access_token"]
    claims = jwt.decode(token, options={"verify_signature": False})
    key = get_settings().jwt_secret.get_secret_value()
    if mutation == "expired":
        claims["exp"] = 1
    elif mutation == "wrong_type":
        claims["type"] = "refresh"
    elif mutation == "wrong_issuer":
        claims["iss"] = "someone-else"
    elif mutation == "missing_exp":
        del claims["exp"]
    elif mutation == "bad_signature":
        key = "other-signing-key-" * 4
    elif mutation == "wrong_user":
        claims["sub"] = str(uuid4())
    invalid = jwt.encode(claims, key, algorithm="HS256")
    assert (
        client.get("/api/v1/users/me", headers={"Authorization": "Bearer " + invalid}).status_code
        == 401
    )


def test_expired_session(context):
    client, connection = context
    payload, user = registration(client)
    token = bearer(login(client, payload))
    connection.execute(
        AuthSession.__table__.update()
        .where(AuthSession.user_id == user["id"])
        .values(expires_at=utcnow() - timedelta(days=1))
    )
    assert client.post("/api/v1/auth/refresh").status_code == 401
    assert client.get("/api/v1/users/me", headers=token).status_code == 401


def test_missing_refresh_and_cross_site_requests(context):
    client, _ = context
    assert client.post("/api/v1/auth/refresh").status_code == 401
    for endpoint in ("refresh", "logout", "login", "register"):
        assert (
            client.post(
                "/api/v1/auth/" + endpoint, json={}, headers={"Origin": "https://evil.example"}
            ).status_code
            == 403
        )
    assert (
        client.post("/api/v1/auth/logout", headers={"Sec-Fetch-Site": "cross-site"}).status_code
        == 403
    )


def test_missing_signing_key_fails_closed(context, monkeypatch):
    client, _ = context
    monkeypatch.setattr(get_settings(), "jwt_secret", SecretStr(""))
    result = client.post("/api/v1/auth/login", json={"username": "whoever", "password": "password"})
    assert result.status_code == 503 and result.json()["code"] == 50302


def test_same_origin_docs_and_secure_cookie(context, monkeypatch):
    client, _ = context
    payload, _ = registration(client)
    monkeypatch.setattr(get_settings(), "cookie_secure", True)
    response = client.post(
        "/api/v1/auth/login",
        json={
            "username": payload["username"],
            "password": PASSWORD,
        },
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200
    assert "secure" in response.headers["set-cookie"].lower()


def test_logout_keeps_other_session_valid(context):
    client, _ = context
    payload, _ = registration(client)
    first = bearer(login(client, payload))
    second = bearer(login(client, payload))
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/users/me", headers=first).status_code == 200
    assert client.get("/api/v1/users/me", headers=second).status_code == 401
