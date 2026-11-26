from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import insert, select
from test_auth import bearer, login, registration
from test_auth import context as context

from app.models import Document, FocusSession, Journal, Note
from app.services import dashboard, focus


@pytest.fixture
def account(context, monkeypatch):
    client, connection = context
    payload, user = registration(client)
    h = bearer(login(client, payload))
    clock = [datetime(2026, 11, 3, 4)]  # Shanghai noon
    monkeypatch.setattr(dashboard, "utcnow", lambda: clock[0])
    monkeypatch.setattr(focus, "utcnow", lambda: clock[0])
    return client, connection, h, user["id"], clock


def read(client, headers):
    response = client.get("/api/v1/dashboard", headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()["data"]


def test_empty_dashboard_and_authentication(account):
    client, _, h, _, _ = account
    result = read(client, h)
    assert result["today"] == "2026-11-03" and result["timezone"] == "Asia/Shanghai"
    assert result["task_total"] == result["task_done"] == result["focus_seconds"] == 0
    assert result["recent_notes"] == result["recent_documents"] == result["tasks"] == []
    assert not result["journal_written"] and result["journal_title"] is None
    assert client.get("/api/v1/dashboard").status_code == 401


def test_task_counts_priority_limit_and_completion(account):
    client, _, h, _, _ = account

    def task(title, **fields):
        response = client.post("/api/v1/tasks", headers=h, json={"title": title, **fields})
        assert response.status_code == 201
        return response.json()["data"]["id"]

    for i in range(6):
        task(f"Low {i}", scheduled_date="2026-11-03", priority="low")
    doing = task("Doing first", due_date="2026-11-03", scheduled_date="2026-11-03", status="doing")
    task("High second", due_date="2026-11-03", priority="high")
    task("Already done", scheduled_date="2026-11-03", status="done")
    task("Overdue", due_date="2026-11-02")
    task("Future", scheduled_date="2026-11-04")
    result = read(client, h)
    assert result["task_total"] == 9 and result["task_done"] == 1
    assert result["overdue_tasks"] == 1 and len(result["tasks"]) == 5
    assert [row["title"] for row in result["tasks"][:2]] == ["Doing first", "High second"]
    assert "description" not in result["tasks"][0]
    assert client.post(f"/api/v1/tasks/{doing}/complete", headers=h).status_code == 200
    assert read(client, h)["task_done"] == 2


def test_local_dashboard_does_not_query_legacy_journal(account, monkeypatch):
    client, connection, h, uid, clock = account
    connection.execute(
        insert(Journal).values(
            id=str(uuid4()),
            user_id=uid,
            entry_date=date(2026, 11, 3),
            title="Legacy private title",
            content="Legacy private body",
            revision=str(uuid4()),
            created_at=clock[0],
            updated_at=clock[0],
        )
    )
    assert read(client, h)["journal_title"] is None

    def forbidden(*args, **kwargs):
        pytest.fail("Local dashboard must not query any legacy journal metadata")

    monkeypatch.setattr(dashboard.repository, "journal_title", forbidden)
    response = client.get("/api/v1/dashboard?include_journal=false", headers=h)
    assert response.status_code == 200
    result = response.json()["data"]
    assert result["journal_title"] is None and not result["journal_written"]
    assert "Legacy private" not in response.text
    forced = client.get("/api/v1/dashboard?include_journal=true", headers=h)
    assert forced.json()["data"]["journal_written"] is None
    assert forced.json()["data"]["journal_source"] == "local"
    assert "Legacy private" not in forced.text
    assert client.get("/api/v1/dashboard?include_journal=false").status_code == 401


def test_recent_metadata_journal_and_owner_isolation(account):
    client, connection, h, uid, clock = account
    for i in range(5):
        stamp = clock[0] - timedelta(minutes=i)
        connection.execute(
            insert(Note).values(
                id=str(uuid4()),
                user_id=uid,
                title=f"Note {i}",
                content="Private body",
                pinned=i == 3,
                revision=str(uuid4()),
                created_at=stamp,
                updated_at=stamp,
            )
        )
        connection.execute(
            insert(Document).values(
                id=str(uuid4()),
                user_id=uid,
                title=f"Doc {i}",
                filename="test.txt",
                kind="text",
                size_bytes=4,
                raw_content=b"body",
                revision=str(uuid4()),
                created_at=stamp,
                updated_at=stamp,
            )
        )
    connection.execute(
        insert(Journal).values(
            id=str(uuid4()),
            user_id=uid,
            entry_date=date(2026, 11, 3),
            title="",
            content="Private journal",
            revision=str(uuid4()),
            created_at=clock[0],
            updated_at=clock[0],
        )
    )
    result = read(client, h)
    assert [n["title"] for n in result["recent_notes"]] == ["Note 0", "Note 1", "Note 2"]
    assert len(result["recent_documents"]) == 3
    assert set(result["recent_notes"][0]) == {"id", "title", "pinned", "updated_at", "storage_mode"}
    assert result["recent_notes"][0]["storage_mode"] == "cloud"
    assert set(result["recent_documents"][0]) == {"id", "title", "kind", "updated_at"}
    assert result["journal_written"] is None and result["journal_title"] is None
    payload, _ = registration(client)
    other = read(client, bearer(login(client, payload)))
    assert other["recent_notes"] == other["recent_documents"] == [] and not other["journal_written"]


def test_focus_running_paused_expired_and_read_only(account):
    client, connection, h, _, clock = account
    timer = client.post(
        "/api/v1/focus/sessions", headers=h, json={"mode": "countdown", "duration_seconds": 60}
    ).json()["data"]
    clock[0] += timedelta(seconds=20)
    result = read(client, h)
    assert result["focus_seconds"] == result["active_focus_seconds"] == 20
    assert result["active_focus_id"] == timer["id"]
    client.post(f"/api/v1/focus/sessions/{timer['id']}/pause", headers=h)
    clock[0] += timedelta(hours=1)
    assert read(client, h)["focus_seconds"] == 20
    client.post(f"/api/v1/focus/sessions/{timer['id']}/resume", headers=h)
    clock[0] += timedelta(minutes=10)
    result = read(client, h)
    assert result["focus_seconds"] == 60 and result["focus_completed"] == 1
    assert (
        connection.execute(
            select(FocusSession.status).where(FocusSession.id == timer["id"])
        ).scalar_one()
        == "running"
    )
    client.get("/api/v1/focus/current", headers=h)
    assert read(client, h)["focus_seconds"] == 60


def test_timezone_midnight_start_day_and_exclusions(account):
    client, connection, h, uid, clock = account
    clock[0] = datetime(2026, 11, 3, 0, 30)
    assert (
        client.patch(
            "/api/v1/users/me", headers=h, json={"timezone": "America/Los_Angeles"}
        ).status_code
        == 200
    )

    def record(start, seconds, kind="focus", status="completed"):
        connection.execute(
            insert(FocusSession).values(
                id=str(uuid4()),
                user_id=uid,
                title="Record",
                mode="stopwatch" if kind == "focus" else "pomodoro",
                kind=kind,
                duration_seconds=None if kind == "focus" else 300,
                status=status,
                elapsed_seconds=seconds,
                started_at=start,
                ended_at=start + timedelta(seconds=seconds),
                updated_at=start,
            )
        )

    record(datetime(2026, 11, 2, 8), 90)  # Nov 2 local start
    record(datetime(2026, 11, 2, 7, 59), 200)  # Nov 1 local start
    record(datetime(2026, 11, 2, 9), 120, status="cancelled")
    record(datetime(2026, 11, 2, 10), 300, kind="break")
    result = read(client, h)
    assert result["today"] == "2026-11-02" and result["focus_seconds"] == 90


def test_future_fixed_timer_is_not_counted_before_actual_start(account):
    client, _, h, _, clock = account
    response = client.post(
        "/api/v1/focus/sessions",
        headers=h,
        json={
            "mode": "scheduled",
            "window_start": "2026-11-03T13:00:00+08:00",
            "window_end": "2026-11-03T14:00:00+08:00",
        },
    )
    assert response.status_code == 201
    assert read(client, h)["active_focus_id"] is None
    clock[0] += timedelta(hours=1, minutes=10)
    result = read(client, h)
    assert result["focus_seconds"] == 600
    assert result["active_focus_id"] == response.json()["data"]["id"]
