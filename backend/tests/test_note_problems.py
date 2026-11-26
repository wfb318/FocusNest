from datetime import datetime

from sqlalchemy import delete
from test_auth import bearer, login, registration
from test_auth import context as context

from app.models.problem import Problem
from app.services import problems


def problem(client, headers, content="怎样理解闭包？"):
    response = client.post("/api/v1/problems", headers=headers, json={"content": content})
    assert response.status_code == 201
    return response.json()["data"]


def note(client, headers, problem_id=None):
    response = client.post(
        "/api/v1/notes",
        headers=headers,
        json={"title": "学习笔记", "content": "记录分析与解决办法。", "problem_id": problem_id},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_link_read_list_preserve_old_client_and_unlink(context):
    client, _ = context
    payload, _ = registration(client)
    h = bearer(login(client, payload))
    p = problem(client, h)
    n = note(client, h, p["id"])
    assert client.get(f"/api/v1/notes/{n['id']}", headers=h).json()["data"]["problem_id"] == p["id"]
    assert (
        client.get("/api/v1/notes", headers=h).json()["data"]["items"][0]["problem_id"] == p["id"]
    )
    result = client.put(
        f"/api/v1/notes/{n['id']}",
        headers=h,
        json={"title": "旧客户端编辑", "content": "保留原关联", "expected_revision": n["revision"]},
    )
    assert result.status_code == 200 and result.json()["data"]["problem_id"] == p["id"]
    result = client.put(
        f"/api/v1/notes/{n['id']}",
        headers=h,
        json={
            "title": "解除关联",
            "content": "正文保留",
            "problem_id": None,
            "expected_revision": result.json()["data"]["revision"],
        },
    )
    assert result.status_code == 200 and result.json()["data"]["problem_id"] is None
    assert result.json()["data"]["content"] == "正文保留"


def test_reject_foreign_missing_and_protect_note_revision(context):
    client, _ = context
    payload, _ = registration(client)
    h = bearer(login(client, payload))
    p = problem(client, h)
    n = note(client, h)
    payload, _ = registration(client)
    other = bearer(login(client, payload))
    assert client.get(f"/api/v1/problems/{p['id']}", headers=other).status_code == 404
    assert (
        client.post(
            "/api/v1/notes",
            headers=other,
            json={"title": "x", "content": "x", "problem_id": p["id"]},
        ).status_code
        == 404
    )
    other_note = note(client, other)
    assert (
        client.put(
            f"/api/v1/notes/{other_note['id']}",
            headers=other,
            json={
                "title": "x",
                "content": "x",
                "problem_id": p["id"],
                "expected_revision": other_note["revision"],
            },
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/notes", headers=h, json={"title": "x", "content": "x", "problem_id": "0" * 36}
        ).status_code
        == 404
    )
    updated = client.put(
        f"/api/v1/notes/{n['id']}",
        headers=h,
        json={
            "title": "x",
            "content": "x",
            "problem_id": p["id"],
            "expected_revision": n["revision"],
        },
    )
    assert updated.status_code == 200
    assert (
        client.put(
            f"/api/v1/notes/{n['id']}",
            headers=h,
            json={
                "title": "x",
                "content": "x",
                "problem_id": None,
                "expected_revision": n["revision"],
            },
        ).status_code
        == 409
    )


def test_status_changes_and_midnight_keep_same_association(context, monkeypatch):
    client, _ = context
    payload, _ = registration(client)
    h = bearer(login(client, payload))
    clock = [datetime(2026, 11, 4, 15, 59)]
    monkeypatch.setattr(problems, "utcnow", lambda: clock[0])
    p = problem(client, h)
    n = note(client, h, p["id"])
    clock[0] = datetime(2026, 11, 4, 16, 1)
    assert (
        client.get("/api/v1/problems", headers=h, params={"bucket": "history"}).json()["data"][
            "items"
        ][0]["id"]
        == p["id"]
    )
    solved = client.patch(
        f"/api/v1/problems/{p['id']}/status",
        headers=h,
        json={"is_resolved": True, "expected_revision": p["revision"]},
    )
    assert solved.status_code == 200
    detail = client.get(f"/api/v1/problems/{p['id']}", headers=h)
    assert detail.headers["cache-control"] == "no-store" and detail.json()["data"]["is_resolved"]
    assert client.get(f"/api/v1/notes/{n['id']}", headers=h).json()["data"]["problem_id"] == p["id"]
    assert client.get(f"/api/v1/problems/{p['id']}").status_code == 401


def test_problem_deletion_clears_link_preserving_note(context):
    client, conn = context
    payload, _ = registration(client)
    h = bearer(login(client, payload))
    p = problem(client, h)
    n = note(client, h, p["id"])
    conn.execute(delete(Problem).where(Problem.id == p["id"]))
    response = client.get(f"/api/v1/notes/{n['id']}", headers=h)
    assert response.status_code == 200 and response.json()["data"]["problem_id"] is None
    assert response.json()["data"]["content"] == n["content"]
