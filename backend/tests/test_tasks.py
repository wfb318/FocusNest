from datetime import datetime, timezone

import pytest
from test_auth import bearer, login, registration
from test_auth import context as context

from app.services import tasks as task_service

BASE = "/api/v1/tasks"


@pytest.fixture
def account(context):
    client, _ = context
    payload, _ = registration(client)
    return client, bearer(login(client, payload))


def create(client, headers, **values):
    response = client.post(BASE, headers=headers, json={"title": "学习任务", **values})
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()["data"]


def test_task_lifecycle_and_partial_update(account):
    client, headers = account
    task = create(
        client,
        headers,
        title="  整理笔记  ",
        description="保留说明",
        priority="high",
        scheduled_date="2026-10-11",
        due_date="2026-10-12",
        estimated_minutes=45,
    )
    url = f"{BASE}/{task['id']}"
    assert task["title"] == "整理笔记"
    assert task["status"] == "todo" and task["completed_at"] is None
    assert "user_id" not in task
    assert task["created_at"].endswith("+00:00")
    assert client.get(url, headers=headers).json()["data"] == task

    patched = client.patch(url, headers=headers, json={"status": "doing"}).json()["data"]
    assert patched["description"] == "保留说明" and patched["scheduled_date"] == "2026-10-11"
    assert patched["status"] == "doing"
    done = client.post(url + "/complete", headers=headers).json()["data"]
    assert done["status"] == "done" and done["completed_at"].endswith("+00:00")
    again = client.post(url + "/complete", headers=headers).json()["data"]
    assert again["completed_at"] == done["completed_at"]
    reopened = client.patch(url, headers=headers, json={"status": "todo"}).json()["data"]
    assert reopened["completed_at"] is None
    cleared = client.patch(
        url,
        headers=headers,
        json={
            "description": None,
            "scheduled_date": None,
            "due_date": None,
            "estimated_minutes": None,
        },
    ).json()["data"]
    assert all(
        cleared[key] is None
        for key in (
            "description",
            "scheduled_date",
            "due_date",
            "estimated_minutes",
        )
    )
    assert client.delete(url, headers=headers).status_code == 200
    assert client.get(url, headers=headers).status_code == 404
    assert client.get(BASE, headers=headers).json()["data"]["total"] == 0


def test_task_owner_isolation_and_unknown_ids(context):
    client, _ = context
    first, _ = registration(client)
    first_headers = bearer(login(client, first))
    task = create(client, first_headers)
    second, _ = registration(client)
    other_headers = bearer(login(client, second))
    assert client.get(BASE, headers=other_headers).json()["data"]["total"] == 0
    for task_id in (task["id"], "missing-task"):
        url = f"{BASE}/{task_id}"
        assert client.get(url, headers=other_headers).status_code == 404
        assert client.patch(url, headers=other_headers, json={"title": "越权"}).status_code == 404
        assert client.post(url + "/complete", headers=other_headers).status_code == 404
        assert client.delete(url, headers=other_headers).status_code == 404
    original = client.get(f"{BASE}/{task['id']}", headers=first_headers).json()["data"]
    assert original["title"] == "学习任务" and original["status"] == "todo"


@pytest.mark.parametrize(
    "values",
    [
        {"title": " "},
        {"title": "x" * 201},
        {"title": None},
        {"status": "invalid"},
        {"status": None},
        {"priority": "urgent"},
        {"priority": None},
        {"estimated_minutes": 0},
        {"estimated_minutes": 10081},
        {"estimated_minutes": 1.5},
        {"estimated_minutes": True},
        {"scheduled_date": "2026-02-30"},
        {"due_date": "not-a-date"},
        {"description": "x" * 10001},
        {"user_id": "someone-else"},
        {"completed_at": "2026-10-11T00:00:00Z"},
    ],
)
def test_task_rejects_invalid_and_protected_fields(account, values):
    client, headers = account
    task = create(client, headers)
    assert client.post(BASE, headers=headers, json={"title": "任务", **values}).status_code == 422
    assert client.patch(f"{BASE}/{task['id']}", headers=headers, json=values).status_code == 422


def test_pagination_and_combined_filters(account):
    client, headers = account
    for n in range(12):
        create(
            client,
            headers,
            title=f"任务{n}",
            priority="high" if n < 3 else "low",
            status="doing" if n < 2 else "todo",
            scheduled_date="2026-10-11",
            due_date="2026-10-12",
        )
    page1 = client.get(BASE, headers=headers, params={"page_size": 5}).json()["data"]
    page2 = client.get(BASE, headers=headers, params={"page_size": 5, "page": 2}).json()["data"]
    assert page1["total"] == page2["total"] == 12
    assert len(page1["items"]) == len(page2["items"]) == 5
    assert {t["id"] for t in page1["items"]}.isdisjoint(t["id"] for t in page2["items"])
    result = client.get(
        BASE,
        headers=headers,
        params={
            "status": "doing",
            "priority": "high",
            "scheduled_date": "2026-10-11",
            "due_date": "2026-10-12",
        },
    ).json()["data"]
    assert result["total"] == 2
    empty = client.get(BASE, headers=headers, params={"page": 99}).json()["data"]
    assert empty["items"] == [] and empty["total"] == 12
    for query in ({"page": 0}, {"page_size": 101}, {"page_size": 0}, {"status": "unknown"}):
        assert client.get(BASE, headers=headers, params=query).status_code == 422


def test_today_uses_user_timezone_and_includes_due_date(account, monkeypatch):
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 11, 0, 30, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(task_service, "datetime", FrozenDateTime)
    client, headers = account
    response = client.patch(
        "/api/v1/users/me", headers=headers, json={"timezone": "America/Los_Angeles"}
    )
    assert response.status_code == 200
    scheduled = create(client, headers, scheduled_date="2026-10-10")
    due = create(client, headers, due_date="2026-10-10", status="done")
    create(client, headers, scheduled_date="2026-10-11")
    create(client, headers)
    result = client.get(BASE, headers=headers, params={"today": True}).json()["data"]
    assert {t["id"] for t in result["items"]} == {scheduled["id"], due["id"]}
    assert due["completed_at"] is not None
    active = client.get(BASE, headers=headers, params={"today": True, "status": "todo"}).json()[
        "data"
    ]
    assert active["total"] == 1


def test_all_task_endpoints_require_login(context):
    client, _ = context
    for method, url, body in (
        ("GET", BASE, None),
        ("POST", BASE, {"title": "任务"}),
        ("GET", BASE + "/missing", None),
        ("PATCH", BASE + "/missing", {"title": "修改"}),
        ("POST", BASE + "/missing/complete", None),
        ("DELETE", BASE + "/missing", None),
    ):
        assert client.request(method, url, json=body).status_code == 401
