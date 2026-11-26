import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models import FocusSession, User
from app.schemas.schedule import ScheduleCreate, ScheduleEdit
from app.schemas.user import Registration
from app.services import auth, schedules


@pytest.mark.skipif(
    os.environ.get("FOCUSNEST_TEST_MYSQL") != "1", reason="Requires real MySQL concurrency"
)
def test_same_occurrence_starts_once_and_edit_revision_wins_once():
    engine = create_engine(get_settings().database_url)
    user_id = None
    try:
        today = datetime.now(timezone.utc).date()
        with Session(engine, expire_on_commit=False) as db:
            name = "schedulerace_" + uuid4().hex[:16]
            user = auth.register(
                db,
                Registration(
                    username=name,
                    email=name + "@example.com",
                    password="Temporary-schedule-race-392!",
                ),
            )
            user_id = user.id
            payload = ScheduleCreate(
                title="Concurrent plan",
                weekday=today.weekday(),
                effective_from=today,
                start_minute=0,
                end_minute=1440,
                timezone="UTC",
                timer_enabled=True,
            )
            sid = schedules.create(db, user, payload)["id"]
        barrier = Barrier(2)

        def start():
            with Session(engine, expire_on_commit=False) as db:
                user = db.get(User, user_id)
                barrier.wait(timeout=10)
                return schedules.start_occurrence(db, user, sid, today).id

        with ThreadPoolExecutor(max_workers=2) as workers:
            ids = list(workers.map(lambda _: start(), range(2)))
        assert ids[0] == ids[1]
        barrier = Barrier(2)

        def edit(title):
            with Session(engine, expire_on_commit=False) as db:
                user = db.get(User, user_id)
                barrier.wait(timeout=10)
                try:
                    schedules.edit(
                        db,
                        user,
                        sid,
                        ScheduleEdit(
                            **{
                                **payload.model_dump(
                                    exclude={"effective_from", "timezone", "repeat_weekly"}
                                ),
                                "title": title,
                            },
                            scope="single",
                            occurrence_date=today,
                            revision=1,
                        ),
                    )
                    return 200
                except AppError as exc:
                    assert exc.code == 40910
                    return 409

        with ThreadPoolExecutor(max_workers=2) as workers:
            statuses = list(workers.map(edit, ("Edit A", "Edit B")))
        assert sorted(statuses) == [200, 409]
        with Session(engine) as db:
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(FocusSession)
                    .where(FocusSession.user_id == user_id)
                )
                == 1
            )
            assert db.get(FocusSession, ids[0]).title == "Concurrent plan"
    finally:
        if user_id:
            with engine.begin() as connection:
                connection.execute(delete(User).where(User.id == user_id))
        engine.dispose()
