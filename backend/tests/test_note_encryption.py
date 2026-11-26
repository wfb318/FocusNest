import os

import pytest
from sqlalchemy import select, update
from test_auth import bearer, login, registration
from test_auth import context as context
from test_notes import create

from app.core.content_crypto import ContentCrypto
from app.core.content_keyring import ContentKeyring, KeyringError
from app.models import Note
from app.services import notes

NOTES = "/api/v1/notes"
TITLE = "受保护的测试标题"
BODY = "# 受保护的测试正文\n行尾  \n"


@pytest.fixture
def account(context, monkeypatch):
    client, connection = context
    payload, _ = registration(client)
    crypto = ContentCrypto(ContentKeyring("test-key", {"test-key": os.urandom(32)}))
    monkeypatch.setattr(notes, "get_content_crypto", lambda: crypto)
    return client, connection, bearer(login(client, payload))


def stored(connection, note_id):
    return connection.execute(select(Note.__table__).where(Note.id == note_id)).mappings().one()


def switch(client, headers, note, mode):
    return client.post(
        f"{NOTES}/{note['id']}/storage",
        headers=headers,
        json={"storage_mode": mode, "expected_revision": note["revision"]},
    )


def test_encrypted_crud_and_private_list_search_dashboard(account):
    client, connection, headers = account
    ordinary = create(client, headers, title=TITLE, content=BODY)
    protected = create(
        client, headers, title=TITLE, content=BODY, pinned=True, storage_mode="cloud_encrypted"
    )
    note_id = protected["id"]
    url = f"{NOTES}/{note_id}"
    row = stored(connection, note_id)
    assert row["title"] is row["content"] is None
    assert TITLE not in row["encrypted_payload"] and BODY not in row["encrypted_payload"]
    assert protected["title"] == TITLE and protected["content"] == BODY
    assert "encrypted_payload" not in protected and "content_revision" not in protected
    assert client.get(url, headers=headers).json()["data"] == protected
    for endpoint, field in ((NOTES, "items"), ("/api/v1/dashboard", "recent_notes")):
        data = client.get(endpoint, headers=headers).json()["data"]
        summary = next(item for item in data[field] if item["id"] == note_id)
        assert summary["title"] == "加密笔记" and summary["storage_mode"] == "cloud_encrypted"
        assert "content" not in summary and "encrypted_payload" not in summary
    search = client.get(NOTES, headers=headers, params={"q": TITLE}).json()["data"]
    assert [item["id"] for item in search["items"]] == [ordinary["id"]]
    edit = {"title": TITLE, "content": BODY + "追加", "expected_revision": protected["revision"]}
    response = client.put(url, headers=headers, json=edit)
    assert response.status_code == 200
    updated = response.json()["data"]
    assert updated["storage_mode"] == "cloud_encrypted" and updated["content"] == edit["content"]
    assert stored(connection, note_id)["encrypted_payload"] != row["encrypted_payload"]
    assert client.put(url, headers=headers, json=edit).status_code == 409
    assert (
        client.delete(url, headers=headers, params={"revision": updated["revision"]}).status_code
        == 200
    )
    assert client.get(url, headers=headers).status_code == 404


def test_explicit_storage_switch_preserves_identity_and_rejects_stale_edits(account):
    client, connection, headers = account
    plain = create(client, headers, title=TITLE, content=BODY)
    url = f"{NOTES}/{plain['id']}"
    fields = {
        "title": TITLE,
        "content": BODY,
        "storage_mode": "cloud_encrypted",
        "expected_revision": plain["revision"],
    }
    assert client.put(url, headers=headers, json=fields).json()["code"] == 40932
    encrypted = switch(client, headers, plain, "cloud_encrypted").json()["data"]
    assert encrypted["revision"] != plain["revision"]
    assert encrypted["created_at"] == plain["created_at"] and encrypted["id"] == plain["id"]
    assert stored(connection, plain["id"])["title"] is None
    assert switch(client, headers, plain, "cloud").status_code == 409
    restored = switch(client, headers, encrypted, "cloud").json()["data"]
    assert restored["content"] == BODY and restored["title"] == TITLE
    row = stored(connection, plain["id"])
    assert row["storage_mode"] == "cloud" and row["encrypted_payload"] is None
    assert row["content_revision"] is None


def test_unavailable_keys_and_failed_readback_keep_original(account, monkeypatch):
    client, connection, headers = account
    plain = create(client, headers, title=TITLE, content=BODY)
    original = dict(stored(connection, plain["id"]))
    crypto = notes.get_content_crypto()

    def unavailable():
        raise KeyringError()

    monkeypatch.setattr(notes, "get_content_crypto", unavailable)
    response = switch(client, headers, plain, "cloud_encrypted")
    assert response.status_code == 503
    assert dict(stored(connection, plain["id"])) == original
    response = client.post(
        NOTES,
        headers=headers,
        json={"title": TITLE, "content": BODY, "storage_mode": "cloud_encrypted"},
    )
    assert response.status_code == 503
    assert client.get(NOTES, headers=headers).json()["data"]["total"] == 1

    monkeypatch.setattr(notes, "get_content_crypto", lambda: crypto)
    monkeypatch.setattr(crypto, "decrypt", lambda *args: b'{"title":"wrong","content":"wrong"}')
    response = switch(client, headers, plain, "cloud_encrypted")
    assert response.status_code == 422
    assert dict(stored(connection, plain["id"])) == original


def test_folder_move_keeps_ciphertext_readable_and_invalidates_open_editor(account):
    client, connection, headers = account
    response = client.post("/api/v1/note-folders", headers=headers, json={"name": "Test folder"})
    folder = response.json()["data"]
    note = create(client, headers, storage_mode="cloud_encrypted", folder_id=folder["id"])
    before = stored(connection, note["id"])
    deleted = client.delete(
        f"/api/v1/note-folders/{folder['id']}",
        headers=headers,
        params={"revision": folder["revision"]},
    )
    assert deleted.status_code == 200
    current = client.get(f"{NOTES}/{note['id']}", headers=headers).json()["data"]
    after = stored(connection, note["id"])
    assert current["folder_id"] is None and current["content"] == note["content"]
    assert current["revision"] != note["revision"]
    assert after["content_revision"] == before["content_revision"]
    assert after["encrypted_payload"] == before["encrypted_payload"]


def test_owner_guard_precedes_decryption_and_corruption_is_isolated(account, monkeypatch):
    client, connection, headers = account
    note = create(client, headers, storage_mode="cloud_encrypted")
    other_payload, _ = registration(client)
    other = bearer(login(client, other_payload))
    url = f"{NOTES}/{note['id']}"
    edit = {"title": TITLE, "content": BODY, "expected_revision": note["revision"]}
    with monkeypatch.context() as isolated:

        def forbidden():
            pytest.fail("Cross-account access must be rejected before loading content keys")

        isolated.setattr(notes, "get_content_crypto", forbidden)
        assert client.get(url, headers=other).status_code == 404
        assert client.put(url, headers=other, json=edit).status_code == 404
        assert switch(client, other, note, "cloud").status_code == 404
        assert (
            client.delete(url, headers=other, params={"revision": note["revision"]}).status_code
            == 404
        )
    connection.execute(
        update(Note).where(Note.id == note["id"]).values(encrypted_payload="damaged")
    )
    for response in (
        client.get(url, headers=headers),
        client.put(url, headers=headers, json=edit),
        switch(client, headers, note, "cloud"),
    ):
        assert response.status_code == 422 and response.json()["code"] == 42230
    assert stored(connection, note["id"])["encrypted_payload"] == "damaged"
    assert client.get(NOTES, headers=headers).status_code == 200
    assert client.get("/api/v1/dashboard", headers=headers).status_code == 200
