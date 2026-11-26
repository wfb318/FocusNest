import os
from urllib.parse import quote, unquote

import pytest
from sqlalchemy import select, update
from test_auth import bearer, login, registration
from test_auth import context as context
from test_document_formats import make_file
from test_documents import upload

from app.core.content_crypto import ContentCrypto
from app.core.content_keyring import ContentKeyring, KeyringError
from app.models import Document, EncryptedJournal
from app.services import documents, encrypted_journals

JOURNALS = "/api/v1/journals/encrypted"
DOCUMENTS = "/api/v1/documents"
JOURNAL_ACCESS = {"X-FocusNest-Journal-Access": "cloud-encrypted"}
DATE = "2026-11-08"
PRIVATE = "验收私密标题"


@pytest.fixture
def account(context, monkeypatch):
    client, connection = context
    payload, _ = registration(client)
    crypto = ContentCrypto(ContentKeyring("workspace-test", {"workspace-test": os.urandom(32)}))
    for service in (documents, encrypted_journals):
        monkeypatch.setattr(service, "get_content_crypto", lambda: crypto)
    return client, connection, bearer(login(client, payload))


def test_opt_in_journal_crud_has_no_plaintext_or_legacy_visibility(account):
    client, connection, owner = account
    headers = {**owner, **JOURNAL_ACCESS}
    path = f"{JOURNALS}/{DATE}"
    data = {"title": PRIVATE, "content": "# 私密日记\n末尾  ", "expected_revision": None}
    assert client.put(path, headers=owner, json=data).status_code == 422
    response = client.put(path, headers=headers, json=data)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    first = response.json()["data"]
    row = (
        connection.execute(
            select(EncryptedJournal.__table__).where(EncryptedJournal.id == first["id"])
        )
        .mappings()
        .one()
    )
    assert "title" not in row and "content" not in row and PRIVATE not in row["encrypted_payload"]
    summary = client.get(JOURNALS, headers=headers, params={"start_date": DATE}).json()["data"]
    assert summary["total"] == 1 and summary["items"][0]["title"] == "加密日记"
    legacy = {**owner, "X-FocusNest-Journal-Access": "legacy-migration"}
    assert client.get("/api/v1/journals", headers=legacy).json()["data"]["total"] == 0
    assert PRIVATE not in client.get("/api/v1/dashboard", headers=owner).text
    assert client.put(path, headers=headers, json=data).status_code == 409
    updated = client.put(
        path,
        headers=headers,
        json={**data, "expected_revision": first["revision"], "content": "更新"},
    ).json()["data"]
    assert updated["revision"] != first["revision"] and updated["content"] == "更新"
    assert client.get(path, headers=headers).json()["data"]["entry"] == updated
    assert (
        client.delete(path, headers=headers, params={"revision": first["revision"]}).status_code
        == 409
    )
    assert (
        client.delete(path, headers=headers, params={"revision": updated["revision"]}).status_code
        == 200
    )
    assert client.get(path, headers=headers).json()["data"]["entry"] is None


def test_journal_owner_and_tampering_guards(account):
    client, connection, owner = account
    headers = {**owner, **JOURNAL_ACCESS}
    path = f"{JOURNALS}/{DATE}"
    data = {"title": PRIVATE, "content": "owner only", "expected_revision": None}
    entry = client.put(path, headers=headers, json=data).json()["data"]
    payload, _ = registration(client)
    other = {**bearer(login(client, payload)), **JOURNAL_ACCESS}
    assert client.get(path, headers=other).json()["data"]["entry"] is None
    assert (
        client.delete(path, headers=other, params={"revision": entry["revision"]}).status_code
        == 404
    )
    connection.execute(
        update(EncryptedJournal)
        .where(EncryptedJournal.id == entry["id"])
        .values(encrypted_payload="bad")
    )
    assert client.get(path, headers=headers).json()["code"] == 42230
    assert (
        client.put(
            path, headers=headers, json={**data, "expected_revision": entry["revision"]}
        ).json()["code"]
        == 42230
    )
    assert client.get(JOURNALS, headers=headers).json()["data"]["total"] == 1


def upload_encrypted(client, headers, filename, raw):
    return client.post(
        DOCUMENTS + "/encrypted-upload",
        headers={
            **headers,
            "Content-Type": "application/octet-stream",
            "X-FocusNest-Filename": quote(filename, safe=""),
        },
        content=raw,
    )


def document_row(connection, document_id):
    return (
        connection.execute(select(Document.__table__).where(Document.id == document_id))
        .mappings()
        .one()
    )


@pytest.mark.parametrize("extension", ["docx", "pdf"])
def test_encrypted_document_original_preview_and_owner(account, extension):
    client, connection, headers = account
    raw = make_file(extension)
    filename = f"{PRIVATE}.{extension}"
    response = upload_encrypted(client, headers, filename, raw)
    assert response.status_code == 201
    item = response.json()["data"]
    assert item["storage_mode"] == "cloud_encrypted" and item["filename"] == filename
    row = document_row(connection, item["id"])
    assert row["title"] is row["filename"] is row["raw_content"] is row["preview_data"] is None
    assert row["encrypted_file"] and row["encrypted_metadata"]
    assert PRIVATE not in row["encrypted_metadata"]
    url = f"{DOCUMENTS}/{item['id']}"
    detail = client.get(url, headers=headers)
    assert detail.json()["data"]["preview"] == item["preview"] and item["preview"] is not None
    download = client.get(url + "/download", headers=headers)
    assert download.content == raw and download.headers["cache-control"] == "no-store"
    assert filename in unquote(download.headers["content-disposition"])
    if extension == "pdf":
        preview = client.get(url + "/preview", headers=headers)
        assert preview.status_code == 200 and preview.content.startswith(b"\x89PNG")
        assert preview.headers["cache-control"] == "no-store"
    else:
        assert "Word <script> text" in str(item["preview"])
    for endpoint in (DOCUMENTS, "/api/v1/dashboard"):
        result = client.get(endpoint, headers=headers)
        assert PRIVATE not in result.text and "加密文档" in result.text
    assert (
        client.get(DOCUMENTS, headers=headers, params={"q": PRIVATE}).json()["data"]["total"] == 0
    )
    payload, _ = registration(client)
    other = bearer(login(client, payload))
    for endpoint in (url, url + "/download", url + "/preview"):
        assert client.get(endpoint, headers=other).status_code == 404
    assert (
        client.post(
            url + "/storage",
            headers=other,
            json={
                "storage_mode": "cloud",
                "expected_revision": item["revision"],
            },
        ).status_code
        == 404
    )
    assert (
        client.delete(url, headers=headers, params={"revision": item["revision"]}).status_code
        == 200
    )


def test_document_storage_change_is_atomic_and_renaming_keeps_file(account, monkeypatch):
    client, connection, headers = account
    raw = "\ufeff# 文档内容\r\n原始字节\r\n".encode()
    plain = upload(client, headers, f"{PRIVATE}.md", raw)
    url = f"{DOCUMENTS}/{plain['id']}"
    change = {"storage_mode": "cloud_encrypted", "expected_revision": plain["revision"]}
    before = dict(document_row(connection, plain["id"]))

    def missing_key():
        raise KeyringError()

    with monkeypatch.context() as override:
        override.setattr(documents, "get_content_crypto", missing_key)
        assert client.post(url + "/storage", headers=headers, json=change).status_code == 503
    assert dict(document_row(connection, plain["id"])) == before

    encrypted = client.post(url + "/storage", headers=headers, json=change).json()["data"]
    assert encrypted["storage_mode"] == "cloud_encrypted"
    assert encrypted["id"] == plain["id"] and encrypted["created_at"] == plain["created_at"]
    assert client.post(url + "/storage", headers=headers, json=change).status_code == 409
    cipher_file = document_row(connection, plain["id"])["encrypted_file"]
    renamed = client.patch(
        url,
        headers=headers,
        json={
            "title": "新标题",
            "expected_revision": encrypted["revision"],
        },
    ).json()["data"]
    assert renamed["title"] == "新标题"
    assert document_row(connection, plain["id"])["encrypted_file"] == cipher_file
    assert client.get(url + "/download", headers=headers).content == raw
    restored = client.post(
        url + "/storage",
        headers=headers,
        json={
            "storage_mode": "cloud",
            "expected_revision": renamed["revision"],
        },
    ).json()["data"]
    assert restored["content"] == raw.decode("utf-8-sig")
    row = document_row(connection, plain["id"])
    assert row["raw_content"] == raw and row["encrypted_file"] is row["encrypted_metadata"] is None


def test_encrypted_upload_limits_and_corrupt_file_fail_closed(account):
    client, connection, headers = account
    over_limit = b"x" * (documents.MAX_DOCUMENT_BYTES + 1)
    assert upload_encrypted(client, headers, "big.pdf", over_limit).status_code == 413
    item = upload_encrypted(client, headers, "small.txt", b"content").json()["data"]
    connection.execute(
        update(Document).where(Document.id == item["id"]).values(encrypted_file="bad")
    )
    url = f"{DOCUMENTS}/{item['id']}"
    assert client.get(url + "/download", headers=headers).json()["code"] == 42230
    assert (
        client.post(
            url + "/storage",
            headers=headers,
            json={
                "storage_mode": "cloud",
                "expected_revision": item["revision"],
            },
        ).json()["code"]
        == 42230
    )
    assert document_row(connection, item["id"])["storage_mode"] == "cloud_encrypted"
