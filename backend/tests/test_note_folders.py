import pytest
from test_auth import bearer, login, registration
from test_auth import context as context


@pytest.fixture
def account(context):
    client, _ = context
    payload, _ = registration(client)
    return client, bearer(login(client, payload))


def folder(client, headers, name, parent_id=None):
    r = client.post(
        "/api/v1/note-folders", headers=headers, json={"name": name, "parent_id": parent_id}
    )
    assert r.status_code == 201, r.text
    assert r.headers["cache-control"] == "no-store"
    return r.json()["data"]


def test_tree_rename_move_delete_preserves_notes(account):
    client, headers = account
    root = folder(client, headers, "学习")
    child = folder(client, headers, "Python", root["id"])
    other = folder(client, headers, "工作")
    assert len(client.get("/api/v1/note-folders", headers=headers).json()["data"]) == 3
    assert (
        client.delete(
            "/api/v1/note-folders/" + root["id"],
            headers=headers,
            params={"revision": root["revision"]},
        ).json()["code"]
        == 40907
    )
    r = client.patch(
        "/api/v1/note-folders/" + child["id"],
        headers=headers,
        json={"name": "代码", "expected_revision": child["revision"]},
    )
    assert r.status_code == 200
    renamed = r.json()["data"]
    assert renamed["revision"] != child["revision"]
    assert (
        client.patch(
            "/api/v1/note-folders/" + child["id"],
            headers=headers,
            json={"name": "旧改名", "expected_revision": child["revision"]},
        ).status_code
        == 409
    )
    body = {"title": "note", "content": "# preserved", "folder_id": child["id"]}
    r = client.post("/api/v1/notes", headers=headers, json=body)
    assert r.status_code == 201
    note = r.json()["data"]
    url = "/api/v1/notes/" + note["id"]
    assert (
        client.get("/api/v1/notes", headers=headers, params={"folder_id": root["id"]}).json()[
            "data"
        ]["total"]
        == 0
    )
    assert (
        client.get("/api/v1/notes", headers=headers, params={"folder_id": child["id"]}).json()[
            "data"
        ]["total"]
        == 1
    )
    assert client.get("/api/v1/notes?unfiled=true", headers=headers).json()["data"]["total"] == 0
    # Older clients omitting folder_id must not remove an existing classification.
    r = client.put(
        url,
        headers=headers,
        json={"title": "note", "content": "# preserved", "expected_revision": note["revision"]},
    )
    assert r.status_code == 200 and r.json()["data"]["folder_id"] == child["id"]
    note = r.json()["data"]
    r = client.put(
        url,
        headers=headers,
        json={**body, "folder_id": other["id"], "expected_revision": note["revision"]},
    )
    assert r.status_code == 200
    moved = r.json()["data"]
    assert (
        client.delete(
            "/api/v1/note-folders/" + other["id"],
            headers=headers,
            params={"revision": other["revision"]},
        ).status_code
        == 200
    )
    preserved = client.get(url, headers=headers).json()["data"]
    assert preserved["folder_id"] is None and preserved["content"] == "# preserved"
    assert preserved["revision"] != moved["revision"]
    assert (
        client.put(
            url, headers=headers, json={**body, "expected_revision": moved["revision"]}
        ).status_code
        == 409
    )
    assert client.get("/api/v1/notes?unfiled=true", headers=headers).json()["data"]["total"] == 1
    assert (
        client.delete(
            "/api/v1/note-folders/" + child["id"],
            headers=headers,
            params={"revision": child["revision"]},
        ).status_code
        == 409
    )
    for item in (renamed, root):
        assert (
            client.delete(
                "/api/v1/note-folders/" + item["id"],
                headers=headers,
                params={"revision": item["revision"]},
            ).status_code
            == 200
        )


def test_ownership_and_duplicate_names(account):
    client, headers = account
    root = folder(client, headers, "主题")
    child = folder(client, headers, "主题", root["id"])
    assert (
        client.post("/api/v1/note-folders", headers=headers, json={"name": "  主题  "}).status_code
        == 409
    )
    other = folder(client, headers, "另一个")
    assert (
        client.patch(
            "/api/v1/note-folders/" + other["id"],
            headers=headers,
            json={"name": "主题", "expected_revision": other["revision"]},
        ).status_code
        == 409
    )
    payload, _ = registration(client)
    outsider = bearer(login(client, payload))
    assert client.get("/api/v1/note-folders", headers=outsider).json()["data"] == []
    assert (
        client.post(
            "/api/v1/note-folders", headers=outsider, json={"name": "窃取", "parent_id": root["id"]}
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/api/v1/notes",
            headers=outsider,
            json={"title": "x", "content": "x", "folder_id": child["id"]},
        ).status_code
        == 404
    )
    assert (
        client.get("/api/v1/notes", headers=outsider, params={"folder_id": root["id"]}).status_code
        == 404
    )
    assert (
        client.delete(
            "/api/v1/note-folders/" + root["id"],
            headers=outsider,
            params={"revision": root["revision"]},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            "/api/v1/note-folders/" + root["id"],
            headers=outsider,
            json={"name": "x", "expected_revision": root["revision"]},
        ).status_code
        == 404
    )
    assert (
        client.get(
            "/api/v1/notes", headers=headers, params={"folder_id": root["id"], "unfiled": True}
        ).status_code
        == 422
    )


@pytest.mark.parametrize("name", ["", "   ", ".", "..", "a/b", "a\\b", "a\nb", "a" * 101])
def test_invalid_names(account, name):
    client, headers = account
    assert (
        client.post("/api/v1/note-folders", headers=headers, json={"name": name}).status_code == 422
    )


def test_folder_endpoints_require_login(context):
    client, _ = context
    assert client.get("/api/v1/note-folders").status_code == 401
    assert client.post("/api/v1/note-folders", json={"name": "x"}).status_code == 401
    assert (
        client.patch(
            "/api/v1/note-folders/id", json={"name": "x", "expected_revision": "x" * 36}
        ).status_code
        == 401
    )
    assert (
        client.delete("/api/v1/note-folders/id", params={"revision": "x" * 36}).status_code == 401
    )
