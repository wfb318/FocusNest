from datetime import datetime

from test_auth import bearer, login, registration
from test_auth import context as context
from test_schedules import account as account
from test_schedules import create, edit_fields, week

BASE = "/api/v1/schedules"
FIRST = "2026-11-02"
SECOND = "2026-11-09"
THIRD = "2026-11-16"


def save(client, headers, start, name):
    response = client.post(
        f"{BASE}/templates", headers=headers, json={"week_start": start, "name": name}
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def apply(client, headers, start, template, expected=None):
    return client.post(
        f"{BASE}/templates/{template['id']}/apply",
        headers=headers,
        json={"week_start": start, "expected_template_id": expected},
    )


def review(client, headers):
    response = client.get(f"{BASE}/template-review", headers=headers)
    assert response.status_code == 200
    return response.json()["data"]


def carry(client, headers):
    response = client.post(f"{BASE}/templates/carry", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]["applied"]


def test_snapshot_and_carry_use_original_template_not_local_edits(account):
    client, headers, clock = account
    create(client, headers, title="Baseline")
    create(
        client,
        headers,
        title="Extra",
        weekday=1,
        effective_from="2026-11-03",
        repeat_weekly=False,
    )
    original = save(client, headers, FIRST, "Study")
    assert original["entry_count"] == 2
    assert apply(client, headers, FIRST, original).status_code == 200
    first_week = week(client, headers, FIRST, "2026-11-08")
    assert [item["title"] for item in first_week] == ["Baseline", "Extra"]
    assert all(not item["repeats"] for item in first_week)

    edited, removed = first_week
    assert (
        client.put(
            f"{BASE}/{edited['schedule_id']}",
            headers=headers,
            json=edit_fields(edited, title="Adjusted for one week"),
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"{BASE}/{removed['schedule_id']}/remove",
            headers=headers,
            json={
                key: value
                for key, value in edit_fields(removed).items()
                if key in {"scope", "occurrence_date", "revision"}
            },
        ).status_code
        == 200
    )
    adjusted = save(client, headers, FIRST, "Adjusted week")
    assert adjusted["entry_count"] == 1
    assert apply(client, headers, FIRST, original, original["id"]).status_code == 200
    assert week(client, headers, FIRST, FIRST)[0]["title"] == "Adjusted for one week"
    assert apply(client, headers, THIRD, adjusted).status_code == 200

    clock[0] = datetime(2026, 11, 7, 15, 59)
    assert review(client, headers) is None
    clock[0] = datetime(2026, 11, 7, 16)
    assert review(client, headers) == {
        "week_start": SECOND,
        "current_template_id": original["id"],
        "planned_template_id": None,
    }
    clock[0] = datetime(2026, 11, 9, 0)
    assert review(client, headers) is None
    assert carry(client, headers)
    assert not carry(client, headers)
    assert [item["title"] for item in week(client, headers, SECOND, "2026-11-15")] == [
        "Baseline",
        "Extra",
    ]
    assert [item["title"] for item in week(client, headers, THIRD, "2026-11-22")] == [
        "Adjusted for one week",
    ]
    assert week(client, headers, FIRST, FIRST)[0]["title"] == "Adjusted for one week"


def test_explicit_sunday_keep_and_change_use_selected_week_only(account):
    client, headers, clock = account
    create(client, headers)
    first = save(client, headers, FIRST, "Standard")
    second = save(client, headers, "2026-10-26", "Free week")
    assert apply(client, headers, FIRST, first).status_code == 200
    clock[0] = datetime(2026, 11, 8, 0)
    create(
        client,
        headers,
        title="Appointment",
        weekday=1,
        effective_from="2026-11-10",
        repeat_weekly=False,
    )
    assert client.post(f"{BASE}/template-review/{SECOND}/keep", headers=headers).status_code == 200
    assert review(client, headers) is None
    assert [item["title"] for item in week(client, headers, SECOND, "2026-11-15")] == [
        "Weekly study",
        "Appointment",
    ]
    assert apply(client, headers, SECOND, second).status_code == 409
    assert apply(client, headers, SECOND, second, first["id"]).status_code == 200
    assert week(client, headers, SECOND, "2026-11-15") == []
    assert len(week(client, headers, FIRST, FIRST)) == 1
    clock[0] = datetime(2026, 11, 15, 0)
    assert review(client, headers)["current_template_id"] == second["id"]
    assert apply(client, headers, THIRD, first).status_code == 200
    assert review(client, headers) is None


def test_template_owner_and_week_validation(account):
    client, headers, _ = account
    other_payload, _ = registration(client)
    other = bearer(login(client, other_payload))
    template = save(client, headers, FIRST, "Protected")
    assert client.get(f"{BASE}/templates", headers=other).json()["data"] == []
    assert apply(client, other, FIRST, template).status_code == 404
    assert apply(client, headers, "2026-11-03", template).status_code == 422
    assert apply(client, headers, "2026-10-26", template).status_code == 422
    assert (
        client.post(
            f"{BASE}/templates", headers=headers, json={"week_start": FIRST, "name": " protected "}
        ).status_code
        == 409
    )
    assert not carry(client, other)
