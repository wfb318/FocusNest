from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, insert, select
from test_auth import bearer, login, registration
from test_auth import context as context

from app.models import FocusSession, Task
from app.services import statistics

BASE = "/api/v1/statistics"


@pytest.fixture
def account(context, monkeypatch):
    client, connection = context
    payload, user = registration(client)
    headers = bearer(login(client, payload))
    now = datetime(2026, 11, 18, 4)
    monkeypatch.setattr(statistics, "utcnow", lambda: now)
    return client, connection, headers, user["id"], now


def read(client, headers, start="2026-11-16", end="2026-11-22"):
    response = client.get(BASE, params={"start_date": start, "end_date": end}, headers=headers)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()["data"]


def seed_focus(connection, user, **changes):
    started = datetime(2026, 11, 17, 2)
    values = dict(
        id=str(uuid4()),
        user_id=user,
        active_user_id=None,
        mode="pomodoro",
        kind="focus",
        status="completed",
        duration_seconds=1500,
        elapsed_seconds=600,
        started_at=started,
        segment_started_at=None,
        ended_at=started + timedelta(minutes=10),
        updated_at=started + timedelta(minutes=10),
    )
    values.update(changes)
    connection.execute(insert(FocusSession).values(**values))
    return values["id"]


def test_empty_default_range_auth_cache_and_private_tables(account):
    client, connection, headers, _, _ = account
    queries = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement.lower())

    event.listen(connection, "before_cursor_execute", capture)
    try:
        response = client.get(BASE, headers=headers)
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    result = response.json()["data"]
    assert result["start_date"] == "2026-11-16" and result["end_date"] == "2026-11-22"
    assert result["timezone"] == "Asia/Shanghai" and result["today"] == "2026-11-18"
    assert result["focus"] == {"seconds": 0, "completed": 0, "active": 0}
    assert len(result["daily"]) == 7 and len(result["modes"]) == 4
    assert all(day["seconds"] == 0 for day in result["daily"])
    assert result["tasks"] == {
        "total": 0,
        "todo": 0,
        "doing": 0,
        "done": 0,
        "overdue": 0,
        "completion_rate": None,
    }
    assert not any(
        name in query
        for query in queries
        for name in ("journals", "notes", "documents", "content_keyring")
    )
    assert client.get(BASE).status_code == 401


def test_focus_is_grouped_by_local_start_day_and_private_owner(account):
    client, connection, headers, uid, _ = account
    _, other = registration(client)
    seed_focus(
        connection,
        uid,
        started_at=datetime(2026, 11, 17, 15, 50),
        ended_at=datetime(2026, 11, 17, 16, 10),
        elapsed_seconds=1200,
    )
    seed_focus(connection, uid, mode="countdown", elapsed_seconds=300)
    seed_focus(connection, uid, mode="stopwatch", duration_seconds=None, elapsed_seconds=90.5)
    seed_focus(connection, uid, kind="break", elapsed_seconds=900)
    seed_focus(connection, uid, status="cancelled", elapsed_seconds=900)
    seed_focus(connection, other["id"], elapsed_seconds=900)
    result = read(client, headers)
    assert result["focus"] == {"seconds": 1590.5, "completed": 3, "active": 0}
    assert result["daily"][1]["seconds"] == 1590.5
    assert sum(day["seconds"] for day in result["daily"]) == result["focus"]["seconds"]
    assert sum(mode["seconds"] for mode in result["modes"]) == result["focus"]["seconds"]
    assert read(client, headers, "2026-11-18", "2026-11-18")["focus"]["seconds"] == 0
    assert all("title" not in mode and "user_id" not in mode for mode in result["modes"])


@pytest.mark.parametrize(
    ("mode", "status", "elapsed", "segment_ago", "start_ago", "end_ago", "expected"),
    [
        ("countdown", "running", 120, 120, 300, None, (240, 0, 1)),
        ("countdown", "running", 120, 300, 600, None, (300, 1, 0)),
        ("pomodoro", "paused", 90, None, 600, None, (90, 0, 1)),
        ("stopwatch", "running", 50, 30, 300, None, (80, 0, 1)),
        ("scheduled", "running", 0, 300, 300, 60, (240, 1, 0)),
        ("scheduled", "scheduled", 0, None, -3600, -7200, (0, 0, 0)),
    ],
)
def test_active_and_elapsed_timers_are_read_without_mutation(
    account,
    mode,
    status,
    elapsed,
    segment_ago,
    start_ago,
    end_ago,
    expected,
):
    client, connection, headers, uid, now = account
    sid = seed_focus(
        connection,
        uid,
        mode=mode,
        status=status,
        active_user_id=uid,
        elapsed_seconds=elapsed,
        duration_seconds=None if mode in ("scheduled", "stopwatch") else 300,
        segment_started_at=now - timedelta(seconds=segment_ago)
        if segment_ago is not None
        else None,
        started_at=now - timedelta(seconds=start_ago),
        window_start=now - timedelta(seconds=start_ago) if mode == "scheduled" else None,
        window_end=now - timedelta(seconds=end_ago) if end_ago is not None else None,
        ended_at=None,
    )
    result = read(client, headers)
    assert tuple(result["focus"].values()) == expected
    stored = connection.execute(
        select(FocusSession.status, FocusSession.elapsed_seconds).where(FocusSession.id == sid)
    ).one()
    assert stored == (status, elapsed)


def test_tasks_are_current_state_of_the_creation_range(account):
    client, connection, headers, uid, now = account
    _, other = registration(client)
    for user, created, status, due in [
        (uid, datetime(2026, 11, 17, 16), "todo", "2026-11-17"),
        (uid, datetime(2026, 11, 18, 0), "doing", "2026-11-18"),
        (uid, datetime(2026, 11, 18, 1), "done", "2026-11-17"),
        (uid, datetime(2026, 11, 17, 15, 59, 59), "done", None),
        (uid, datetime(2026, 11, 18, 16), "todo", None),
        (other["id"], now, "done", None),
    ]:
        connection.execute(
            insert(Task).values(
                id=str(uuid4()),
                user_id=user,
                title="Synthetic private task",
                status=status,
                created_at=created,
                updated_at=created,
                due_date=date.fromisoformat(due) if due else None,
            )
        )
    result = read(client, headers, "2026-11-18", "2026-11-18")
    assert result["tasks"] == {
        "total": 3,
        "todo": 1,
        "doing": 1,
        "done": 1,
        "overdue": 1,
        "completion_rate": 33.3,
    }
    assert "Synthetic private task" not in str(result)


def test_dst_day_covers_both_repeated_hours_and_excludes_next_midnight(account):
    client, connection, headers, uid, _ = account
    response = client.patch(
        "/api/v1/users/me", headers=headers, json={"timezone": "America/New_York"}
    )
    assert response.status_code == 200
    for hour in (4, 5, 6):
        seed_focus(connection, uid, started_at=datetime(2026, 11, 1, hour), elapsed_seconds=60)
    seed_focus(connection, uid, started_at=datetime(2026, 11, 2, 4, 59), elapsed_seconds=60)
    seed_focus(connection, uid, started_at=datetime(2026, 11, 2, 5), elapsed_seconds=999)
    result = read(client, headers, "2026-11-01", "2026-11-01")
    assert result["timezone"] == "America/New_York"
    assert result["focus"]["seconds"] == 240 and result["focus"]["completed"] == 4


def test_leap_year_maximum_range_is_filled_without_truncation(account):
    client, _, headers, _, _ = account
    result = read(client, headers, "2024-01-01", "2024-12-31")
    assert len(result["daily"]) == 366
    assert result["daily"][59]["date"] == "2024-02-29"
    assert result["daily"][-1]["date"] == "2024-12-31"


@pytest.mark.parametrize(
    "query",
    [
        "?start_date=2026-11-01",
        "?end_date=2026-11-01",
        "?start_date=2026-11-02&end_date=2026-11-01",
        "?start_date=2025-01-01&end_date=2026-01-02",
        "?start_date=invalid&end_date=2026-11-18",
        "?start_date=9999-12-31&end_date=9999-12-31",
    ],
)
def test_invalid_range_is_rejected(account, query):
    client, _, headers, _, _ = account
    response = client.get(BASE + query, headers=headers)
    assert response.status_code == 422
