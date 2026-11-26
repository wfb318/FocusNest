import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update
from test_auth import bearer, login, registration
from test_auth import context as context
from test_journals import legacy, seed

from app.models import Journal
from app.schemas.journal import JournalRead
from app.services.journals import source_digest


@pytest.fixture
def account(context):
    client, connection = context
    payload, user = registration(client)
    seed(connection, user["id"])
    headers = legacy(bearer(login(client, payload)))
    entry = client.get("/api/v1/journals/2026-11-05", headers=headers).json()["data"]["entry"]
    body = {
        "expected_revision": entry["revision"],
        "verified_source_digest": source_digest(JournalRead.model_validate(entry)),
        "local_revision": "a" * 64,
        "confirmation": "DELETE_CLOUD_COPY",
    }
    return client, connection, headers, user["id"], body


def test_unicode_digest_matches_frontend_fixture():
    data = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "frontend/tests/fixtures/journalTransferDigest.json"
        ).read_text(encoding="utf-8")
    )
    assert source_digest(JournalRead.model_validate(data["entry"])) == data["digest"]


def test_separate_cleanup_requires_auth_intent_confirmation_and_exact_source(account):
    client, connection, h, uid, payload = account
    url = "/api/v1/journals/2026-11-05/migration-cleanup"
    assert client.post(url, json=payload).status_code == 401
    assert (
        client.post(
            url,
            headers={key: value for key, value in h.items() if key != "X-FocusNest-Journal-Access"},
            json=payload,
        ).status_code
        == 403
    )
    for override in (
        {"confirmation": "NO"},
        {"local_revision": "bad"},
        {"content": "Must not accept plaintext"},
    ):
        assert client.post(url, headers=h, json={**payload, **override}).status_code == 422
    for override in ({"expected_revision": str(uuid4())}, {"verified_source_digest": "0" * 64}):
        assert client.post(url, headers=h, json={**payload, **override}).status_code == 409
    assert (
        connection.scalar(select(func.count()).select_from(Journal).where(Journal.user_id == uid))
        == 1
    )


def test_cleanup_deletes_only_owned_matching_row_and_is_retry_safe(account):
    client, connection, h, uid, payload = account
    seed(connection, uid, day="2026-11-04")
    other_payload, other = registration(client)
    other_headers = legacy(bearer(login(client, other_payload)))
    seed(connection, other["id"])
    url = "/api/v1/journals/2026-11-05/migration-cleanup"
    other_result = client.post(url, headers=other_headers, json=payload)
    assert other_result.status_code == 409
    assert client.post(url, headers=h, json=payload).json()["data"] == {
        "removed": True,
        "already_missing": False,
    }
    assert client.post(url, headers=h, json=payload).json()["data"] == {
        "removed": True,
        "already_missing": True,
    }
    assert (
        connection.scalar(select(func.count()).select_from(Journal).where(Journal.user_id == uid))
        == 1
    )
    assert (
        connection.scalar(
            select(func.count()).select_from(Journal).where(Journal.user_id == other["id"])
        )
        == 1
    )


def test_source_body_change_without_revision_change_also_blocks_cleanup(account):
    client, connection, h, uid, payload = account
    connection.execute(update(Journal).where(Journal.user_id == uid).values(content="Changed body"))
    response = client.post("/api/v1/journals/2026-11-05/migration-cleanup", headers=h, json=payload)
    assert response.status_code == 409
    assert "Changed body" not in response.text
    assert (
        connection.scalar(select(Journal.content).where(Journal.user_id == uid)) == "Changed body"
    )
