import importlib.util
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import jwt
import pytest
from sqlalchemy import event, insert, select, update
from sqlalchemy.orm import Session
from test_auth import PASSWORD, bearer, login, registration
from test_auth import context as context

from app.core.security import decode_access_token, password_hasher, signing_key
from app.models import AuthSession, User
from app.models.user import utcnow
from app.services import admin as service

BASE = "/api/v1/admin"
PRESENCE = "/api/v1/users/me/heartbeat"


@pytest.fixture
def administrator(context):
    client, connection = context
    payload, account = registration(client)
    connection.execute(update(User).where(User.id == account["id"]).values(role="admin"))
    headers = bearer(login(client, payload))
    return client, connection, headers, account["id"]


def read(client, headers, path="/overview", **params):
    response = client.get(BASE + path, params=params, headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()["data"]


def test_admin_endpoints_require_live_server_side_role(context):
    client, connection = context
    payload, account = registration(client, "admin")
    assert account["role"] == "user"
    response = login(client, payload)
    headers = bearer(response)
    for path in ("/overview", "/users"):
        anonymous = client.get(BASE + path)
        assert anonymous.status_code == 401
        assert anonymous.headers["cache-control"] == "no-store"
        denied = client.get(BASE + path, headers=headers)
        assert denied.status_code == 403 and denied.json()["code"] == 40340
        assert denied.headers["cache-control"] == "no-store"
    claims = decode_access_token(response.json()["data"]["access_token"])
    claims["role"] = "admin"
    fake_role = jwt.encode(claims, signing_key(), algorithm="HS256")
    assert (
        client.get(BASE + "/users", headers={"Authorization": "Bearer " + fake_role}).status_code
        == 403
    )
    connection.execute(update(User).where(User.id == account["id"]).values(role="admin"))
    assert client.get(BASE + "/overview", headers=headers).status_code == 200
    connection.execute(update(User).where(User.id == account["id"]).values(role="user"))
    assert client.get(BASE + "/overview", headers=headers).status_code == 403
    assert client.get("/api/v1/users/me", headers=headers).json()["data"]["role"] == "user"


@pytest.mark.parametrize("field,value", [("role", "admin"), ("is_admin", True)])
def test_registration_and_profile_cannot_assign_roles(context, field, value):
    client, _ = context
    payload = {"username": "attempt_admin", "email": "attempt@example.com", "password": PASSWORD}
    response = client.post("/api/v1/auth/register", json={**payload, field: value})
    assert response.status_code == 422 and PASSWORD not in response.text
    payload, _ = registration(client)
    headers = bearer(login(client, payload))
    assert client.patch("/api/v1/users/me", json={field: value}, headers=headers).status_code == 422


def test_overview_respects_admin_timezone_and_registration_boundaries(administrator, monkeypatch):
    client, connection, headers, admin_id = administrator
    now = datetime(2026, 11, 25, 16, 30)  # Nov 26 00:30 in Asia/Shanghai.
    monkeypatch.setattr(service, "utcnow", lambda: now)
    connection.execute(
        update(User).where(User.id == admin_id).values(created_at=now - timedelta(minutes=1))
    )
    dates = (
        datetime(2026, 11, 25, 15, 59),
        datetime(2026, 11, 25, 16),
        datetime(2026, 11, 22, 16),
        datetime(2026, 11, 22, 15, 59),
        datetime(2026, 10, 31, 16),
        datetime(2026, 10, 31, 15, 59),
        now + timedelta(minutes=1),
    )
    for created in dates:
        _, account = registration(client)
        connection.execute(update(User).where(User.id == account["id"]).values(created_at=created))
    result = read(client, headers)
    assert result["timezone"] == "Asia/Shanghai" and result["today"] == "2026-11-26"
    assert result["registered_total"] == 8 and result["administrators"] == 1
    assert result["registered_today"] == 2
    assert result["registered_week"] == 4
    assert result["registered_month"] == 6
    assert result["server_now"].endswith("+00:00")
    assert result["online_window_seconds"] == 300


def seed_session(connection, uid, now, seen, **changes):
    values = {
        "id": str(uuid4()),
        "user_id": uid,
        "refresh_token_hash": uuid4().hex * 2,
        "created_at": now - timedelta(days=1),
        "expires_at": now + timedelta(days=1),
        "last_seen_at": seen,
        "revoked_at": None,
    }
    values.update(changes)
    connection.execute(insert(AuthSession).values(**values))


def test_online_deduplicates_sessions_and_excludes_revoked_expired_stale_future(
    administrator, monkeypatch
):
    client, connection, headers, _ = administrator
    now = utcnow()
    monkeypatch.setattr(service, "utcnow", lambda: now)
    connection.execute(update(AuthSession).values(last_seen_at=None))
    ids = []
    for _ in range(7):
        _, account = registration(client)
        ids.append(account["id"])
    seed_session(connection, ids[0], now, now)
    seed_session(connection, ids[0], now, now - timedelta(seconds=20))
    seed_session(connection, ids[1], now, now - timedelta(seconds=301))
    seed_session(connection, ids[2], now, now, revoked_at=now)
    seed_session(connection, ids[3], now, now, expires_at=now)
    seed_session(connection, ids[4], now, now + timedelta(seconds=1))
    seed_session(connection, ids[5], now, None)
    seed_session(connection, ids[6], now, now - timedelta(seconds=300))
    assert read(client, headers)["online_users"] == 2
    online = read(client, headers, "/users", online=True)
    assert online["total"] == 2
    assert {row["id"] for row in online["items"]} == {ids[0], ids[6]}
    assert all(row["online"] for row in online["items"])
    offline = read(client, headers, "/users", online=False)
    assert offline["total"] == 6
    assert not any(row["online"] for row in offline["items"])


def test_presence_is_authenticated_rate_limited_and_does_not_touch_other_accounts(
    administrator, monkeypatch
):
    client, connection, admin_headers, _ = administrator
    payload, account = registration(client)
    response = login(client, payload)
    headers = bearer(response)
    session_id = decode_access_token(response.json()["data"]["access_token"])["sid"]
    now = utcnow()
    monkeypatch.setattr(service, "utcnow", lambda: now)
    connection.execute(update(AuthSession).values(last_seen_at=None))
    assert client.post(PRESENCE).status_code == 401
    assert client.post(PRESENCE, json={"user_id": "another"}, headers=headers).status_code == 422
    result = client.post(PRESENCE, json={}, headers=headers)
    assert result.status_code == 200 and result.headers["cache-control"] == "no-store"
    assert result.json()["data"]["online_window_seconds"] == 300
    assert (
        connection.execute(
            select(AuthSession.last_seen_at).where(AuthSession.id == session_id)
        ).scalar_one()
        == now
    )
    assert (
        connection.execute(
            select(AuthSession.id).where(
                AuthSession.user_id != account["id"], AuthSession.last_seen_at.is_not(None)
            )
        ).all()
        == []
    )
    monkeypatch.setattr(service, "utcnow", lambda: now + timedelta(seconds=10))
    assert client.post(PRESENCE, headers=headers).status_code == 200
    assert (
        connection.execute(
            select(AuthSession.last_seen_at).where(AuthSession.id == session_id)
        ).scalar_one()
        == now
    )
    monkeypatch.setattr(service, "utcnow", lambda: now + timedelta(seconds=31))
    assert client.post(PRESENCE, headers=headers).status_code == 200
    assert connection.execute(
        select(AuthSession.last_seen_at).where(AuthSession.id == session_id)
    ).scalar_one() == now + timedelta(seconds=31)
    assert read(client, admin_headers)["online_users"] == 1
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.post(PRESENCE, headers=headers).status_code == 401
    assert read(client, admin_headers)["online_users"] == 0


def test_admin_list_filters_paginates_and_never_exposes_private_contents(administrator):
    client, connection, headers, _ = administrator
    member, account = registration(client, "member_under")
    member_headers = bearer(login(client, member))
    note = client.post(
        "/api/v1/notes",
        headers=member_headers,
        json={"title": "private-admin-test-title", "content": "private-admin-test-body"},
    )
    assert note.status_code == 201, note.text
    assert (
        client.get("/api/v1/notes/" + note.json()["data"]["id"], headers=headers).status_code == 404
    )
    queries = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement.lower())

    event.listen(connection, "before_cursor_execute", capture)
    try:
        overview = read(client, headers)
        page = read(client, headers, "/users", page_size=1)
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert overview["registered_total"] == 2 and page["total"] == 2
    assert len(page["items"]) == 1
    assert set(page["items"][0]) == {
        "id",
        "username",
        "email",
        "nickname",
        "role",
        "created_at",
        "last_login_at",
        "last_seen_at",
        "online",
    }
    assert not any(
        name in query for query in queries for name in ("notes", "journals", "documents")
    )
    assert "private-admin-test" not in str(page) + str(overview)
    second = read(client, headers, "/users", page_size=1, page=2)
    assert second["items"][0]["id"] != page["items"][0]["id"]
    assert read(client, headers, "/users", search="member_under")["items"][0]["id"] == account["id"]
    assert read(client, headers, "/users", search="%")["total"] == 0
    assert read(client, headers, "/users", search="_")["total"] == 2  # Both test names contain _.
    assert read(client, headers, "/users", role="admin")["total"] == 1
    assert read(client, headers, "/users", role="user")["total"] == 1
    assert read(client, headers, "/users", page=100)["items"] == []


@pytest.mark.parametrize(
    "params",
    [{"page": 0}, {"page_size": 101}, {"role": "root"}, {"search": "x" * 101}, {"online": "maybe"}],
)
def test_admin_query_validation_is_private(administrator, params):
    client, _, headers, _ = administrator
    result = client.get(BASE + "/users", params=params, headers=headers)
    assert result.status_code == 422
    assert result.headers["cache-control"] == "no-store"


def cli_module(monkeypatch, connection):
    path = Path(__file__).resolve().parents[1] / "scripts" / "manage_admin.py"
    spec = importlib.util.spec_from_file_location("focusnest_admin_cli_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(
        module,
        "SessionLocal",
        lambda: Session(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ),
    )
    return module


def test_cli_creates_independent_hashed_admin_and_supports_revocation(context, monkeypatch, capsys):
    client, connection = context
    member, member_account = registration(client)
    module = cli_module(monkeypatch, connection)
    name = "Admin_CLI_" + uuid4().hex[:10]
    monkeypatch.setattr(module, "getpass", lambda prompt: PASSWORD)
    assert module.main(["create", "--username", name, "--email", name + "@example.com"]) == 0
    role, stored_hash = connection.execute(
        select(User.role, User.password_hash).where(User.username == name)
    ).one()
    assert role == "admin" and password_hasher.verify(PASSWORD, stored_hash)
    assert (
        connection.execute(select(User.role).where(User.id == member_account["id"])).scalar_one()
        == "user"
    )
    result = login(client, {"username": name, "password": PASSWORD})
    assert result.json()["data"]["user"]["username"] == name
    assert client.get(BASE + "/overview", headers=bearer(result)).status_code == 200
    users = read(client, bearer(result), "/users", search=name.lower())
    assert users["items"][0]["username"] == name
    assert module.main(["revoke", "--identity", name.lower()]) == 0
    assert client.get(BASE + "/overview", headers=bearer(result)).status_code == 403
    assert module.main(["grant", "--identity", name.upper()]) == 0
    assert module.main(
        ["create", "--username", name.lower(), "--email", "other_" + name + "@example.com"]
    ) == 1
    output = capsys.readouterr()
    assert PASSWORD not in output.out + output.err
    assert stored_hash not in output.out + output.err


def test_cli_rejects_invalid_or_mismatched_passwords_without_leaking_them(
    context, monkeypatch, capsys
):
    _, connection = context
    module = cli_module(monkeypatch, connection)
    passwords = iter(("private-invalid-short", "different-confirmation"))
    monkeypatch.setattr(module, "getpass", lambda prompt: next(passwords))
    assert module.main(["create", "--username", "cli_mismatch", "--email", "cli@example.com"]) == 1
    monkeypatch.setattr(module, "getpass", lambda prompt: "short")
    assert module.main(["create", "--username", "cli_invalid", "--email", "cli@example.com"]) == 1
    assert (
        connection.execute(
            select(User.id).where(User.username.in_(("cli_mismatch", "cli_invalid")))
        ).all()
        == []
    )
    output = capsys.readouterr()
    assert "private-invalid-short" not in output.out + output.err
    assert "input_value" not in output.out + output.err
