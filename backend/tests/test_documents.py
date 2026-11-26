from urllib.parse import unquote

import pytest
from test_auth import bearer, login, registration
from test_auth import context as context


@pytest.fixture
def account(context):
    client, _ = context
    payload, _ = registration(client)
    return client, bearer(login(client, payload))


def upload(
    client, headers, filename="资料.md", content=b"# resource\r\n\r\n    code\r\nline  \r\n"
):
    r = client.post(
        "/api/v1/documents", headers=headers, files={"file": (filename, content, "text/plain")}
    )
    assert r.status_code == 201, r.text
    assert r.headers["cache-control"] == "no-store"
    return r.json()["data"]


def test_lifecycle_download_and_stale_versions(account):
    client, headers = account
    raw = "\ufeff# 外部资料😀\r\n\r\n    code\r\nline  \r\n".encode()
    first = upload(client, headers, filename="外部资料.MD", content=raw)
    assert first["title"] == "外部资料" and first["kind"] == "markdown"
    assert first["size_bytes"] == len(raw) and first["content"] == raw.decode("utf-8-sig")
    assert "user_id" not in first and "raw_content" not in first
    url = "/api/v1/documents/" + first["id"]
    assert client.get(url, headers=headers).json()["data"] == first
    r = client.get(url + "/download", headers=headers)
    assert r.content == raw
    assert "外部资料.MD" in unquote(r.headers["content-disposition"])
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-type"] == "application/octet-stream"
    update = {"title": "  新标题  ", "expected_revision": first["revision"]}
    r = client.patch(url, headers=headers, json=update)
    assert r.status_code == 200
    renamed = r.json()["data"]
    assert renamed["title"] == "新标题" and renamed["filename"] == first["filename"]
    assert renamed["revision"] != first["revision"]
    assert client.get(url + "/download", headers=headers).content == raw
    assert client.patch(url, headers=headers, json=update).status_code == 409
    assert (
        client.delete(url, headers=headers, params={"revision": first["revision"]}).status_code
        == 409
    )
    assert (
        client.delete(url, headers=headers, params={"revision": renamed["revision"]}).status_code
        == 200
    )
    assert client.get(url, headers=headers).status_code == 404
    assert client.get(url + "/download", headers=headers).status_code == 404


def test_ownership(account):
    client, headers = account
    first = upload(client, headers)
    payload, _ = registration(client)
    other = bearer(login(client, payload))
    url = "/api/v1/documents/" + first["id"]
    assert client.get("/api/v1/documents", headers=other).json()["data"]["total"] == 0
    for path in (url, url + "/download"):
        assert client.get(path, headers=other).status_code == 404
    assert (
        client.patch(
            url, headers=other, json={"title": "steal", "expected_revision": first["revision"]}
        ).status_code
        == 404
    )
    assert (
        client.delete(url, headers=other, params={"revision": first["revision"]}).status_code == 404
    )
    assert client.get(url, headers=headers).json()["data"] == first


@pytest.mark.parametrize(
    "filename, raw, status",
    [
        ("a.pdf", b"fake", 422),
        ("a.docx", b"fake", 422),
        ("a.exe.md", b"a\0b", 422),
        ("a.md", b"", 422),
        ("a.txt", b" \n\t", 422),
        ("a.txt", bytes([255, 254, 97, 0]), 422),
        ("a.md", b"x" * (512 * 1024 + 1), 413),
        ("a.md", ("字" * 100001).encode(), 422),
        ("x" * 256 + ".txt", b"body", 422),
    ],
    ids=[
        "pdf",
        "word",
        "binary",
        "empty",
        "blank",
        "utf16",
        "oversize",
        "too_many_chars",
        "long_filename",
    ],
)
def test_invalid_upload(account, filename, raw, status):
    client, headers = account
    r = client.post(
        "/api/v1/documents", headers=headers, files={"file": (filename, raw, "text/plain")}
    )
    assert r.status_code == status, r.text
    assert client.get("/api/v1/documents", headers=headers).json()["data"]["total"] == 0


def test_search_type_pagination_and_untrusted_path(account):
    client, headers = account
    first = upload(client, headers, "100%_literal.txt", b"first")
    upload(client, headers, "middle.markdown")
    third = upload(client, headers, "../../safe.txt", b"last")
    assert third["filename"] == "safe.txt"
    page = client.get("/api/v1/documents?page_size=2", headers=headers).json()["data"]
    assert page["total"] == 3 and len(page["items"]) == 2 and page["items"][0]["id"] == third["id"]
    assert all("content" not in item and "raw_content" not in item for item in page["items"])
    second = client.get("/api/v1/documents?page_size=2&page=2", headers=headers).json()["data"]
    assert second["items"][0]["id"] == first["id"]
    for params, expected in [
        ({"q": "%_"}, 1),
        ({"kind": "markdown"}, 1),
        ({"kind": "text"}, 2),
        ({"q": "safe", "kind": "text"}, 1),
    ]:
        assert (
            client.get("/api/v1/documents", headers=headers, params=params).json()["data"]["total"]
            == expected
        )
    for params in ({"page": 0}, {"page_size": 101}, {"kind": "unknown"}, {"q": "x" * 101}):
        assert client.get("/api/v1/documents", headers=headers, params=params).status_code == 422


def test_long_unicode_exact_download_and_same_names(account):
    client, headers = account
    raw = ("😀" * 100000).encode()
    first = upload(client, headers, "same.md", raw)
    second = upload(client, headers, "same.md", raw)
    assert first["id"] != second["id"]
    assert (
        client.get("/api/v1/documents/" + first["id"] + "/download", headers=headers).content == raw
    )


def test_rename_validation_and_missing_file(account):
    client, headers = account
    first = upload(client, headers)
    url = "/api/v1/documents/" + first["id"]
    for values in (
        {"title": " "},
        {"title": "x" * 201},
        {"title": None},
        {"title": "x\ny"},
        {"user_id": "bad"},
        {"filename": "new.md"},
        {"raw_content": "bad"},
        {"expected_revision": "bad"},
    ):
        r = client.patch(
            url,
            headers=headers,
            json={"title": "valid", "expected_revision": first["revision"], **values},
        )
        assert r.status_code == 422
    assert client.delete(url, headers=headers).status_code == 422
    assert client.post("/api/v1/documents", headers=headers).status_code == 422


def test_endpoints_require_auth(context):
    client, _ = context
    for path in ("", "/missing", "/missing/download"):
        assert client.get("/api/v1/documents" + path).status_code == 401
    assert client.post("/api/v1/documents", files={"file": ("a.txt", b"a")}).status_code == 401
    assert (
        client.patch(
            "/api/v1/documents/missing", json={"title": "x", "expected_revision": "x" * 36}
        ).status_code
        == 401
    )
    assert (
        client.delete("/api/v1/documents/missing", params={"revision": "x" * 36}).status_code == 401
    )


def test_filename_control_validation_before_storage():
    from app.core.exceptions import AppError
    from app.services.documents import validate_file

    with pytest.raises(AppError) as exc:
        validate_file("bad\x01.txt", b"body")
    assert exc.value.status_code == 422


def test_percent_encoded_filename_stays_literal(account):
    client, headers = account
    # HTTP clients may escape control bytes in multipart headers; do not unquote them into paths.
    document = upload(client, headers, "bad%01.txt", b"body")
    assert document["filename"] == "bad%01.txt"
