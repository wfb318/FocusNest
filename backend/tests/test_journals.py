from datetime import date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select
from test_auth import bearer, login, registration
from test_auth import context as context

from app.core.exceptions import AppError
from app.models import Journal
from app.services import journals


@pytest.fixture
def account(context):
    client, connection = context
    payload, user = registration(client)
    return client, connection, bearer(login(client, payload)), user["id"]


def legacy(headers):
    return {**headers, "X-FocusNest-Journal-Access": "legacy-migration"}


def seed(connection, uid, day="2026-11-05", title="Legacy title", content="Legacy body"):
    key = str(uuid4())
    connection.execute(
        insert(Journal).values(
            id=key,
            user_id=uid,
            entry_date=date.fromisoformat(day),
            title=title,
            content=content,
            revision=str(uuid4()),
            created_at=datetime(2026, 11, 5),
            updated_at=datetime(2026, 11, 5),
        )
    )
    return key


def test_legacy_reads_require_explicit_intent_and_keep_owner_isolation(account):
    client, connection, h, uid = account
    seed(connection, uid)
    for path in ("", "/today", "/2026-11-05"):
        response = client.get("/api/v1/journals" + path, headers=h)
        assert response.status_code == 403
        assert "Legacy title" not in response.text and "Legacy body" not in response.text
    headers = legacy(h)
    restored = client.get("/api/v1/journals/2026-11-05", headers=headers)
    assert restored.status_code == 200
    assert restored.headers["cache-control"] == "no-store"
    assert restored.json()["data"]["entry"]["content"] == "Legacy body"
    payload, _ = registration(client)
    other = legacy(bearer(login(client, payload)))
    assert client.get("/api/v1/journals", headers=other).json()["data"]["total"] == 0
    assert client.get("/api/v1/journals/2026-11-05", headers=other).json()["data"]["entry"] is None


@pytest.mark.parametrize(
    "body",
    [
        b'{"content":"private draft","title":"private title"}',
        b"{broken private input",
        b"",
        b"null",
    ],
)
def test_cloud_write_and_delete_denied_without_echo_or_database_change(account, body):
    client, connection, h, uid = account
    seed(connection, uid)
    for headers in (h, legacy(h), {**h, "X-FocusNest-Storage-Mode": "cloud"}):
        response = client.put("/api/v1/journals/2026-11-05", headers=headers, content=body)
        assert response.status_code == 403 and response.json()["code"] == 40321
        assert "private" not in response.text
        assert client.delete("/api/v1/journals/2026-11-05", headers=headers).status_code == 403
    assert (
        connection.scalar(select(func.count()).select_from(Journal).where(Journal.user_id == uid))
        == 1
    )
    assert connection.scalar(select(Journal.content).where(Journal.user_id == uid)) == "Legacy body"


def test_legacy_filters_pagination_and_invalid_dates(account):
    client, connection, h, uid = account
    for number in range(1, 5):
        seed(
            connection,
            uid,
            day=f"2026-11-0{number}",
            content="literal %_" if number == 2 else "body",
        )
    headers = legacy(h)
    result = client.get("/api/v1/journals?page_size=2", headers=headers).json()["data"]
    assert result["total"] == 4 and len(result["items"]) == 2
    assert "content" not in result["items"][0]
    result = client.get("/api/v1/journals?q=%25_", headers=headers).json()["data"]
    assert result["total"] == 1
    for query in (
        "page=0",
        "page_size=101",
        "start_date=bad",
        "start_date=0001-01-01",
        "start_date=2026-11-05&end_date=2026-11-01",
    ):
        assert client.get("/api/v1/journals?" + query, headers=headers).status_code == 422


def test_internal_cloud_mutations_also_fail_closed():
    with pytest.raises(AppError) as error:
        journals.save(None, None, date(2026, 11, 5), None)
    assert error.value.status_code == 403
    with pytest.raises(AppError):
        journals.delete_entry(None, None, date(2026, 11, 5), "revision")


def test_endpoints_still_require_login(context):
    client, _ = context
    for path in ("", "/today", "/2026-11-05"):
        assert (
            client.get(
                "/api/v1/journals" + path,
                headers={"X-FocusNest-Journal-Access": "legacy-migration"},
            ).status_code
            == 401
        )
    assert client.put("/api/v1/journals/2026-11-05", json={"content": "x"}).status_code == 401
    assert client.delete("/api/v1/journals/2026-11-05").status_code == 401
