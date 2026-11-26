from datetime import datetime, timedelta

import pytest
from test_auth import bearer, login, registration
from test_auth import context as context

from app.services import focus, schedules


@pytest.fixture
def account(context, monkeypatch):
    client, _ = context
    payload, _ = registration(client)
    headers = bearer(login(client, payload))
    clock = [datetime(2026, 11, 2, 0, 0)]  # Monday 08:00 in Shanghai
    monkeypatch.setattr(focus, "utcnow", lambda: clock[0])
    monkeypatch.setattr(schedules, "utcnow", lambda: clock[0])
    return client, headers, clock


def create(client, headers, **changes):
    data = dict(
        title="Weekly study",
        weekday=0,
        start_minute=540,
        end_minute=600,
        timezone="Asia/Shanghai",
        effective_from="2026-11-02",
        timer_enabled=True,
    )
    result = client.post("/api/v1/schedules", headers=headers, json={**data, **changes})
    assert result.status_code == 201, result.text
    assert result.headers["cache-control"] == "no-store"
    return result.json()["data"]["id"]


def week(client, headers, start="2026-11-02", end="2026-11-23"):
    result = client.get(f"/api/v1/schedules?start_date={start}&end_date={end}", headers=headers)
    assert result.status_code == 200, result.text
    return result.json()["data"]["items"]


def edit_fields(item, **changes):
    return (
        {
            name: item[name]
            for name in (
                "title",
                "notes",
                "start_minute",
                "end_minute",
                "task_id",
                "timer_enabled",
                "remind_start",
                "remind_end",
                "weekday",
                "occurrence_date",
                "revision",
            )
        }
        | {"scope": "single"}
        | changes
    )


def test_repeat_single_edit_skip_restore_and_revision(account):
    client, h, _ = account
    sid = create(client, h)
    rows = week(client, h)
    assert len(rows) == 4 and rows[0]["starts_at"] == "2026-11-02T01:00:00Z"
    changed = client.put(
        f"/api/v1/schedules/{sid}", headers=h, json=edit_fields(rows[1], title="This week only")
    )
    assert changed.status_code == 200
    rows = week(client, h)
    assert [r["title"] for r in rows] == [
        "Weekly study",
        "This week only",
        "Weekly study",
        "Weekly study",
    ]
    stale = client.put(f"/api/v1/schedules/{sid}", headers=h, json=edit_fields(rows[1], revision=1))
    assert stale.status_code == 409
    remove = client.post(
        f"/api/v1/schedules/{sid}/remove",
        headers=h,
        json={
            "scope": "single",
            "occurrence_date": rows[1]["occurrence_date"],
            "revision": rows[1]["revision"],
        },
    )
    assert remove.status_code == 200
    rows = week(client, h)
    assert rows[1]["skipped"] and not rows[2]["skipped"]
    assert (
        client.put(f"/api/v1/schedules/{sid}", headers=h, json=edit_fields(rows[1])).status_code
        == 200
    )
    assert not week(client, h)[1]["skipped"]


@pytest.mark.parametrize("repeat_weekly", [False, True])
def test_create_repeat_choice_controls_later_occurrences(account, repeat_weekly):
    client, headers, _ = account
    schedule_id = create(
        client,
        headers,
        weekday=2,
        effective_from="2026-11-04",
        repeat_weekly=repeat_weekly,
    )
    rows = [item for item in week(client, headers) if item["schedule_id"] == schedule_id]
    expected = ["2026-11-04", "2026-11-11", "2026-11-18"] if repeat_weekly else ["2026-11-04"]
    assert [item["occurrence_date"] for item in rows] == expected
    assert all(item["repeats"] is repeat_weekly for item in rows)


def test_future_split_and_remove_keep_past(account):
    client, h, clock = account
    sid = create(client, h)
    rows = week(client, h)
    clock[0] += timedelta(days=7)
    assert (
        client.put(f"/api/v1/schedules/{sid}", headers=h, json=edit_fields(rows[0])).status_code
        == 422
    )
    assert (
        client.put(
            f"/api/v1/schedules/{sid}",
            headers=h,
            json=edit_fields(rows[1], scope="future", title="New plan"),
        ).status_code
        == 200
    )
    rows = week(client, h)
    assert [r["title"] for r in rows] == ["Weekly study", "New plan", "New plan", "New plan"]
    assert rows[0]["schedule_id"] != rows[1]["schedule_id"]
    assert (
        client.post(
            f"/api/v1/schedules/{rows[2]['schedule_id']}/remove",
            headers=h,
            json={
                "scope": "future",
                "occurrence_date": rows[2]["occurrence_date"],
                "revision": rows[2]["revision"],
            },
        ).status_code
        == 200
    )
    assert len(week(client, h)) == 2


def test_auto_start_late_activation_idempotence_and_finish(account):
    client, h, clock = account
    sid = create(client, h)
    url = f"/api/v1/schedules/{sid}/start?occurrence_date=2026-11-02"
    assert client.post(url, headers=h).status_code == 409
    clock[0] = datetime(2026, 11, 2, 1, 20)
    result = client.post(url, headers=h)
    assert result.status_code == 200, result.text
    timer = result.json()["data"]
    assert timer["elapsed_seconds"] == 0 and timer["window_start"] == "2026-11-02T01:00:00+00:00"
    clock[0] += timedelta(minutes=10)
    repeated = client.post(url, headers=h).json()["data"]
    assert repeated["id"] == timer["id"] and repeated["elapsed_seconds"] == 600
    assert client.post(f"/api/v1/focus/sessions/{timer['id']}/pause", headers=h).status_code == 409
    # Early completion must not accumulate more time or restart this occurrence.
    finished = client.post(f"/api/v1/focus/sessions/{timer['id']}/finish", headers=h).json()["data"]
    clock[0] += timedelta(minutes=5)
    repeated = client.post(url, headers=h).json()["data"]
    assert (
        repeated["id"] == timer["id"]
        and repeated["elapsed_seconds"] == finished["elapsed_seconds"] == 600
    )
    assert repeated["status"] == "completed"


def test_timer_conflict_and_task_ownership(account):
    client, h, clock = account
    sid = create(client, h)
    timer = client.post("/api/v1/focus/sessions", headers=h, json={"mode": "stopwatch"}).json()[
        "data"
    ]
    clock[0] += timedelta(hours=1)
    assert (
        client.post(
            f"/api/v1/schedules/{sid}/start?occurrence_date=2026-11-02", headers=h
        ).status_code
        == 409
    )
    assert client.get("/api/v1/focus/current", headers=h).json()["data"]["id"] == timer["id"]
    payload, _ = registration(client)
    other = bearer(login(client, payload))
    assert week(client, other) == []
    assert (
        client.post(
            f"/api/v1/schedules/{sid}/start?occurrence_date=2026-11-02", headers=other
        ).status_code
        == 404
    )
    task = client.post("/api/v1/tasks", headers=h, json={"title": "Private"}).json()["data"]
    response = client.post(
        "/api/v1/schedules",
        headers=other,
        json=dict(
            title="Foreign",
            weekday=0,
            start_minute=540,
            end_minute=600,
            timezone="Asia/Shanghai",
            effective_from="2026-11-02",
            task_id=task["id"],
        ),
    )
    assert response.status_code == 404


def test_fixed_window_wait_restore_expiry_and_cancel(account):
    client, h, clock = account
    timer = client.post(
        "/api/v1/focus/sessions",
        headers=h,
        json=dict(
            mode="scheduled",
            title="Planned",
            window_start="2026-11-02T09:00:00+08:00",
            window_end="2026-11-02T10:00:00+08:00",
        ),
    ).json()["data"]
    assert timer["status"] == "scheduled" and timer["elapsed_seconds"] == 0
    assert client.post(f"/api/v1/focus/sessions/{timer['id']}/finish", headers=h).status_code == 409
    assert client.post("/api/v1/focus/sessions", headers=h, json={}).status_code == 409
    clock[0] += timedelta(hours=1, minutes=30)
    active = client.get("/api/v1/focus/current", headers=h).json()["data"]
    assert active["status"] == "running" and active["elapsed_seconds"] == 1800
    clock[0] += timedelta(days=1)
    assert client.get("/api/v1/focus/current", headers=h).json()["data"] is None
    record = client.get("/api/v1/focus/sessions", headers=h).json()["data"]["items"][0]
    assert record["elapsed_seconds"] == 3600 and record["ended_at"] == "2026-11-02T02:00:00+00:00"


@pytest.mark.parametrize(
    "changes",
    [
        dict(start_minute=600, end_minute=500),
        dict(weekday=7),
        dict(title=" "),
        dict(timezone="no/such-zone"),
        dict(effective_from="2026-11-01"),
        dict(start_minute=True),
        dict(user_id="foreign"),
    ],
)
def test_invalid_plan(account, changes):
    client, h, _ = account
    value = (
        dict(
            title="Plan",
            weekday=0,
            start_minute=540,
            end_minute=600,
            timezone="Asia/Shanghai",
            effective_from="2026-11-02",
        )
        | changes
    )
    assert client.post("/api/v1/schedules", headers=h, json=value).status_code == 422


def test_timezones_dst_and_range_validation(account):
    client, h, _ = account
    create(client, h, weekday=6, start_minute=150, end_minute=210, timezone="America/New_York")
    rows = week(client, h, "2027-03-14", "2027-03-14")
    assert rows[0]["time_warning"] and rows[0]["starts_at"] is None
    assert (
        client.get(
            "/api/v1/schedules?start_date=2026-11-02&end_date=2027-11-02", headers=h
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/schedules?start_date=2026-11-02&end_date=2026-11-01", headers=h
        ).status_code
        == 422
    )
    assert (
        client.get("/api/v1/schedules?start_date=2026-11-02&end_date=2026-11-03").status_code == 401
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"window_start": "2026-11-02T10:00:00+08:00"},
        {"window_start": "2026-11-02T09:00:00"},
        {"window_end": "2026-11-02T07:00:00+08:00"},
        {"duration_seconds": 600},
        {"kind": "break"},
    ],
)
def test_invalid_fixed_times(account, changes):
    client, h, _ = account
    value = (
        dict(
            mode="scheduled",
            window_start="2026-11-02T09:00:00+08:00",
            window_end="2026-11-02T10:00:00+08:00",
        )
        | changes
    )
    assert client.post("/api/v1/focus/sessions", headers=h, json=value).status_code == 422
