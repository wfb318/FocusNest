import pytest
from test_auth import bearer, login, registration
from test_auth import context as context


@pytest.fixture
def account(context):
    client, _ = context
    payload, _ = registration(client)
    return client, bearer(login(client, payload))


def create(client, headers, **values):
    response = client.post(
        "/api/v1/notes", headers=headers, json={"title": "知识", "content": "# Markdown", **values}
    )
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()["data"]


def test_lifecycle_and_stale_writes(account):
    client, headers = account
    note = create(client, headers, title="  学习  ")
    assert note["title"] == "学习" and note["pinned"] is False
    assert note["created_at"].endswith("+00:00") and "user_id" not in note
    url = "/api/v1/notes/" + note["id"]
    assert client.get(url, headers=headers).json()["data"] == note
    payload = {
        "title": "改名",
        "content": "    code\nline  \n",
        "pinned": True,
        "expected_revision": note["revision"],
    }
    response = client.put(url, headers=headers, json=payload)
    assert response.status_code == 200
    updated = response.json()["data"]
    assert updated["content"] == payload["content"] and updated["pinned"] is True
    assert updated["revision"] != note["revision"]
    assert client.put(url, headers=headers, json=payload).status_code == 409
    assert (
        client.delete(url, headers=headers, params={"revision": note["revision"]}).status_code
        == 409
    )
    assert (
        client.delete(url, headers=headers, params={"revision": updated["revision"]}).status_code
        == 200
    )
    assert client.get(url, headers=headers).status_code == 404
    assert client.put(url, headers=headers, json=payload).status_code == 404


def test_ownership(account):
    client, headers = account
    note = create(client, headers)
    payload, _ = registration(client)
    other = bearer(login(client, payload))
    url = "/api/v1/notes/" + note["id"]
    assert client.get("/api/v1/notes", headers=other).json()["data"]["total"] == 0
    assert client.get(url, headers=other).status_code == 404
    assert (
        client.put(
            url,
            headers=other,
            json={"title": "steal", "content": "steal", "expected_revision": note["revision"]},
        ).status_code
        == 404
    )
    assert (
        client.delete(url, headers=other, params={"revision": note["revision"]}).status_code == 404
    )
    assert client.get(url, headers=headers).json()["data"] == note


@pytest.mark.parametrize(
    "values",
    [
        {"title": ""},
        {"title": "  "},
        {"title": None},
        {"title": "字" * 201},
        {"content": ""},
        {"content": "\n\t"},
        {"content": None},
        {"content": "字" * 100001},
        {"pinned": "true"},
        {"pinned": 1},
        {"user_id": "forged"},
        {"id": "forged"},
        {"revision": "forged"},
        {"expected_revision": "x" * 36},
    ],
)
def test_create_validation(account, values):
    client, headers = account
    assert (
        client.post(
            "/api/v1/notes", headers=headers, json={"title": "标题", "content": "正文", **values}
        ).status_code
        == 422
    )
    assert client.get("/api/v1/notes", headers=headers).json()["data"]["total"] == 0


def test_update_requires_revision_and_valid_fields(account):
    client, headers = account
    note = create(client, headers)
    url = "/api/v1/notes/" + note["id"]
    for values in (
        {},
        {"expected_revision": None},
        {"expected_revision": "bad"},
        {"expected_revision": note["revision"], "title": "  "},
    ):
        assert (
            client.put(
                url, headers=headers, json={"title": "标题", "content": "正文", **values}
            ).status_code
            == 422
        )
    assert client.delete(url, headers=headers).status_code == 422


def test_search_pin_pagination_and_long_content(account):
    client, headers = account
    first = create(client, headers, pinned=True, content="100%_literal")
    second = create(client, headers, title="第二篇")
    content = "笔记😀" * 25000
    third = create(client, headers, content=content)
    assert (
        client.get("/api/v1/notes/" + third["id"], headers=headers).json()["data"]["content"]
        == content
    )
    result = client.get("/api/v1/notes?page_size=2", headers=headers).json()["data"]
    assert result["total"] == 3 and [n["id"] for n in result["items"]] == [first["id"], third["id"]]
    assert all("content" not in n for n in result["items"])
    result = client.get("/api/v1/notes?page_size=2&page=2", headers=headers).json()["data"]
    assert [n["id"] for n in result["items"]] == [second["id"]]
    for params, total in [
        ({"q": "%_"}, 1),
        ({"q": "第二"}, 1),
        ({"pinned": True}, 1),
        ({"pinned": False}, 2),
        ({"pinned": True, "q": "第二"}, 0),
    ]:
        assert (
            client.get("/api/v1/notes", headers=headers, params=params).json()["data"]["total"]
            == total
        )
    for params in ({"page": 0}, {"page_size": 101}, {"q": "x" * 101}, {"pinned": "bad"}):
        assert client.get("/api/v1/notes", headers=headers, params=params).status_code == 422


def test_requires_auth(context):
    client, _ = context
    for method, path, kwargs in [
        ("get", "", {}),
        ("get", "/missing", {}),
        ("post", "", {"json": {"title": "a", "content": "b"}}),
        (
            "put",
            "/missing",
            {"json": {"title": "a", "content": "b", "expected_revision": "x" * 36}},
        ),
        ("delete", "/missing", {"params": {"revision": "x" * 36}}),
    ]:
        assert getattr(client, method)("/api/v1/notes" + path, **kwargs).status_code == 401
