from datetime import datetime, timedelta

import pytest
from test_auth import bearer, login, registration
from test_auth import context as context

from app.services import focus


@pytest.fixture
def account(context, monkeypatch):
    client, _ = context
    payload, _ = registration(client)
    headers = bearer(login(client, payload))
    clock = [datetime(2026, 10, 16, 4, 0, 0)]
    monkeypatch.setattr(focus, "utcnow", lambda: clock[0])
    return client, headers, clock


def start(client, headers, **values):
    result = client.post("/api/v1/focus/sessions", headers=headers, json=values)
    assert result.status_code == 201, result.text
    assert result.headers["cache-control"] == "no-store"
    return result.json()["data"]


def action(client, headers, session, name):
    result = client.post(f"/api/v1/focus/sessions/{session['id']}/{name}", headers=headers)
    assert result.status_code == 200, result.text
    return result.json()["data"]


def test_pause_resume_reload_and_idempotent_finish(account):
    client, headers, clock = account
    session = start(client, headers, mode="stopwatch")
    clock[0] += timedelta(seconds=12.5)
    paused = action(client, headers, session, "pause")
    assert paused["elapsed_seconds"] == 12.5
    clock[0] += timedelta(hours=2)
    assert action(client, headers, session, "pause")["elapsed_seconds"] == 12.5
    restored = client.get("/api/v1/focus/current", headers=headers).json()["data"]
    assert restored["id"] == session["id"] and restored["status"] == "paused"
    action(client, headers, session, "resume")
    clock[0] += timedelta(seconds=7.5)
    assert action(client, headers, session, "resume")["elapsed_seconds"] == 20
    finished = action(client, headers, session, "finish")
    assert finished["status"] == "completed" and finished["elapsed_seconds"] == 20
    clock[0] += timedelta(minutes=1)
    for name in ("finish", "cancel", "resume", "pause"):
        repeated = action(client, headers, session, name)
        assert repeated["ended_at"] == finished["ended_at"]
        assert repeated["status"] == "completed" and repeated["elapsed_seconds"] == 20
    assert client.get("/api/v1/focus/current", headers=headers).json()["data"] is None


def test_expired_timer_clamps_elapsed_and_allows_new_start(account):
    client, headers, clock = account
    session = start(client, headers, mode="countdown", duration_seconds=60)
    clock[0] += timedelta(seconds=20)
    action(client, headers, session, "pause")
    clock[0] += timedelta(seconds=100)
    action(client, headers, session, "resume")
    clock[0] += timedelta(days=1)
    new = start(client, headers, mode="stopwatch")
    history = client.get("/api/v1/focus/sessions", headers=headers).json()["data"]
    old = next(item for item in history["items"] if item["id"] == session["id"])
    assert old["status"] == "completed" and old["elapsed_seconds"] == 60
    assert old["ended_at"] == "2026-10-16T04:02:40+00:00"
    assert new["status"] == "running"


def test_current_read_settles_expiration_and_cancel_preserves_time(account):
    client, headers, clock = account
    start(client, headers, duration_seconds=60)
    clock[0] += timedelta(seconds=61)
    assert client.get("/api/v1/focus/current", headers=headers).json()["data"] is None
    session = start(client, headers, mode="stopwatch")
    clock[0] += timedelta(seconds=11)
    cancelled = action(client, headers, session, "cancel")
    assert cancelled["status"] == "cancelled" and cancelled["elapsed_seconds"] == 11
    assert action(client, headers, session, "finish")["status"] == "cancelled"
    start(client, headers)


def test_one_active_including_paused_and_break_defaults(account):
    client, headers, _ = account
    session = start(client, headers)
    assert session["duration_seconds"] == 1500
    for _ in range(2):
        assert client.post("/api/v1/focus/sessions", headers=headers, json={}).status_code == 409
        action(client, headers, session, "pause")
    action(client, headers, session, "finish")
    rest = start(client, headers, kind="break")
    assert rest["duration_seconds"] == 300 and rest["task_id"] is None


def test_task_ownership_and_deleted_task_preserves_history(account):
    client, headers, _ = account
    task = client.post("/api/v1/tasks", headers=headers, json={"title": "Focus task"}).json()[
        "data"
    ]
    session = start(client, headers, task_id=task["id"])
    payload, _ = registration(client)
    other = bearer(login(client, payload))
    assert (
        client.post(
            "/api/v1/focus/sessions", headers=other, json={"task_id": task["id"]}
        ).status_code
        == 404
    )
    for name in ("pause", "resume", "finish", "cancel"):
        assert (
            client.post(f"/api/v1/focus/sessions/{session['id']}/{name}", headers=other).status_code
            == 404
        )
    assert client.get("/api/v1/focus/current", headers=other).json()["data"] is None
    assert client.get("/api/v1/focus/sessions", headers=other).json()["data"]["total"] == 0
    assert client.delete(f"/api/v1/tasks/{task['id']}", headers=headers).status_code == 200
    restored = client.get("/api/v1/focus/current", headers=headers).json()["data"]
    assert restored["id"] == session["id"] and restored["task_id"] is None
    assert "user_id" not in restored and "active_user_id" not in restored


@pytest.mark.parametrize(
    "payload",
    [
        {"mode": "invalid"},
        {"kind": "invalid"},
        {"duration_seconds": 0},
        {"duration_seconds": 86401},
        {"duration_seconds": True},
        {"duration_seconds": 60.1},
        {"duration_seconds": "60"},
        {"mode": "stopwatch", "duration_seconds": 60},
        {"kind": "break", "mode": "stopwatch"},
        {"kind": "break", "task_id": "foreign"},
        {"user_id": "foreign"},
        {"elapsed_seconds": 1000},
        {"status": "completed"},
    ],
)
def test_invalid_inputs(account, payload):
    client, headers, _ = account
    assert client.post("/api/v1/focus/sessions", headers=headers, json=payload).status_code == 422
    assert client.get("/api/v1/focus/current", headers=headers).json()["data"] is None


def test_history_pagination_and_query_validation(account):
    client, headers, clock = account
    for _ in range(3):
        session = start(client, headers)
        action(client, headers, session, "finish")
        clock[0] += timedelta(seconds=1)
    first = client.get("/api/v1/focus/sessions?page_size=2", headers=headers).json()["data"]
    second = client.get("/api/v1/focus/sessions?page_size=2&page=2", headers=headers).json()["data"]
    assert first["total"] == 3 and len(first["items"]) == 2 and len(second["items"]) == 1
    assert not {x["id"] for x in first["items"]} & {x["id"] for x in second["items"]}
    for query in ("page=0", "page_size=101", "page_size=0"):
        assert client.get("/api/v1/focus/sessions?" + query, headers=headers).status_code == 422


def test_all_endpoints_require_login(context):
    client, _ = context
    for path in ("current", "sessions"):
        assert client.get("/api/v1/focus/" + path).status_code == 401
    assert client.post("/api/v1/focus/sessions", json={}).status_code == 401
    for name in ("pause", "resume", "finish", "cancel"):
        assert client.post(f"/api/v1/focus/sessions/missing/{name}").status_code == 401
