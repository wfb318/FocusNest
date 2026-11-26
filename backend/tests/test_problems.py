from datetime import datetime, timedelta

import pytest
from sqlalchemy import insert
from test_auth import bearer, login, registration
from test_auth import context as context

from app.models.problem import Problem
from app.services import problems


@pytest.fixture
def account(context, monkeypatch):
    client, connection = context
    payload, user = registration(client)
    headers = bearer(login(client, payload))
    clock = [datetime(2026, 11, 4, 15, 59)]  # Shanghai 23:59
    monkeypatch.setattr(problems, "utcnow", lambda: clock[0])
    return client, connection, headers, user["id"], clock


def create(client, h, content="为什么函数返回 None？"):
    response = client.post("/api/v1/problems", headers=h, json={"content": content})
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()["data"]


def listing(client, h, bucket="today", **params):
    response = client.get("/api/v1/problems", headers=h, params={"bucket": bucket, **params})
    assert response.status_code == 200, response.text
    return response.json()["data"]


def status(client, h, item, resolved):
    response = client.patch(
        f"/api/v1/problems/{item['id']}/status",
        headers=h,
        json={"is_resolved": resolved, "expected_revision": item["revision"]},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_midnight_history_resolve_reopen_and_original_dates(account):
    client, _, h, _, clock = account
    first = create(client, h)
    assert listing(client, h)["counts"] == {"today": 1, "history": 0, "resolved": 0, "all": 1}
    clock[0] += timedelta(minutes=2)
    assert listing(client, h)["total"] == 0
    history = listing(client, h, "history")
    assert history["items"][0]["created_at"] == first["created_at"]
    solved = status(client, h, first, True)
    assert solved["resolved_at"] == "2026-11-04T16:01:00+00:00"
    assert listing(client, h, "history")["total"] == 0
    assert listing(client, h, "resolved")["total"] == 1
    clock[0] += timedelta(hours=1)
    repeated = status(client, h, solved, True)
    assert repeated["resolved_at"] == solved["resolved_at"]
    reopened = status(client, h, repeated, False)
    assert reopened["resolved_at"] is None and reopened["created_at"] == first["created_at"]
    assert listing(client, h, "history")["total"] == 1
    res = client.put(
        f"/api/v1/problems/{first['id']}",
        headers=h,
        json={"content": "补充尝试过的方法", "expected_revision": reopened["revision"]},
    )
    assert res.status_code == 200 and res.json()["data"]["created_at"] == first["created_at"]
    assert (
        client.put(
            f"/api/v1/problems/{first['id']}",
            headers=h,
            json={"content": "stale", "expected_revision": first["revision"]},
        ).status_code
        == 409
    )


def test_owner_isolation_and_authentication(account):
    client, _, h, _, _ = account
    item = create(client, h)
    payload, _ = registration(client)
    other = bearer(login(client, payload))
    assert listing(client, other, "all")["total"] == 0
    for method, suffix, value in (
        ("put", "", {"content": "foreign"}),
        ("patch", "/status", {"is_resolved": True}),
    ):
        assert (
            getattr(client, method)(
                f"/api/v1/problems/{item['id']}{suffix}",
                headers=other,
                json={**value, "expected_revision": item["revision"]},
            ).status_code
            == 404
        )
    assert "为什么" not in client.get("/api/v1/problems/export", headers=other).text
    assert client.get("/api/v1/problems").status_code == 401
    assert client.post("/api/v1/problems", json={"content": "no auth"}).status_code == 401
    assert client.get("/api/v1/problems/export").status_code == 401


def test_export_all_filtered_unicode_and_fences(account):
    client, _, h, _, clock = account
    content = "中文疑问\n```\n# 不应该成为导出标题\n````\n保留原文  "
    first = create(client, h, content)
    clock[0] += timedelta(minutes=2)
    create(client, h, "今日问题")
    status(client, h, first, True)
    response = client.get("/api/v1/problems/export", headers=h, params={"bucket": "all"})
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert (
        response.content.startswith(b"\xef\xbb\xbf")
        and ".md" in response.headers["content-disposition"]
    )
    text = response.content.decode("utf-8-sig")
    assert "共 2 条" in text and "- [x] 已解决" in text and "- [ ] 今日问题" in text
    assert content in text and "`````text" in text and "解决：2026-11-05 00:01:00 +0800" in text
    filtered = client.get(
        "/api/v1/problems/export", headers=h, params={"bucket": "resolved", "q": "中文"}
    ).text
    assert "共 1 条" in filtered and "今日问题" not in filtered


def test_search_literal_wildcards_and_pagination(account):
    client, _, h, _, clock = account
    for value in ("100% 为什么", "100_ 为什么", "普通问题"):
        create(client, h, value)
        clock[0] += timedelta(seconds=1)
    assert listing(client, h, q="%")["total"] == 1
    assert listing(client, h, q="_")["total"] == 1
    assert listing(client, h, page_size=2)["items"][0]["content"] == "普通问题"
    assert len(listing(client, h, page_size=2, page=2)["items"]) == 1
    assert (
        client.get("/api/v1/problems", headers=h, params={"bucket": "invalid"}).status_code == 422
    )
    assert client.get("/api/v1/problems", headers=h, params={"page_size": 101}).status_code == 422


@pytest.mark.parametrize("value", ["", "  \n ", "x" * 10001])
def test_invalid_content(account, value):
    client, _, h, _, _ = account
    assert client.post("/api/v1/problems", headers=h, json={"content": value}).status_code == 422


def test_timezone_boundary_and_rejected_client_timestamps(account):
    client, _, h, _, _ = account
    create(client, h)
    assert (
        client.patch(
            "/api/v1/users/me", headers=h, json={"timezone": "America/Los_Angeles"}
        ).status_code
        == 200
    )
    assert listing(client, h)["today"] == "2026-11-04"
    assert (
        client.post(
            "/api/v1/problems", headers=h, json={"content": "bad", "created_at": "2000-01-01"}
        ).status_code
        == 422
    )


def test_export_limit_rejects_instead_of_silent_truncation(account):
    client, conn, h, uid, clock = account
    from uuid import uuid4

    conn.execute(
        insert(Problem),
        [
            dict(
                id=str(uuid4()),
                user_id=uid,
                content="问题",
                is_resolved=False,
                revision=str(uuid4()),
                created_at=clock[0],
                updated_at=clock[0],
            )
            for _ in range(1001)
        ],
    )
    response = client.get("/api/v1/problems/export", headers=h)
    assert response.status_code == 413 and response.json()["code"] == 41302
