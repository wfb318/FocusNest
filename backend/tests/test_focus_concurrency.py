import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models import FocusSession, User
from app.schemas.focus import FocusCreate
from app.schemas.user import Registration
from app.services import auth, focus


@pytest.mark.skipif(
    os.environ.get("FOCUSNEST_TEST_MYSQL") != "1", reason="Requires real MySQL concurrency"
)
def test_simultaneous_start_and_terminal_race():
    engine = create_engine(get_settings().database_url)
    user_id = None
    try:
        with Session(engine, expire_on_commit=False) as db:
            name = "focusrace_" + uuid4().hex[:18]
            user = auth.register(
                db,
                Registration(
                    username=name, email=name + "@example.com", password="Temporary-focus-392!"
                ),
            )
            user_id = user.id
        barrier = Barrier(2)

        def start_once():
            with Session(engine, expire_on_commit=False) as db:
                current_user = db.get(User, user_id)
                barrier.wait(timeout=10)
                try:
                    return focus.start(db, current_user, FocusCreate(mode="stopwatch")).id
                except AppError as exc:
                    assert exc.status_code == 409
                    return None

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(lambda _: start_once(), range(2)))
        assert results.count(None) == 1
        session_id = next(result for result in results if result)
        barrier = Barrier(2)

        def transition_once(action):
            with Session(engine, expire_on_commit=False) as db:
                current_user = db.get(User, user_id)
                barrier.wait(timeout=10)
                return focus.transition(db, current_user, session_id, action)

        with ThreadPoolExecutor(max_workers=2) as workers:
            list(workers.map(transition_once, ("pause", "finish")))
        with Session(engine) as db:
            saved = db.get(FocusSession, session_id)
            assert saved.status == "completed" and saved.active_user_id is None
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(FocusSession)
                    .where(FocusSession.user_id == user_id)
                )
                == 1
            )
    finally:
        if user_id:
            with engine.begin() as connection:
                connection.execute(delete(FocusSession).where(FocusSession.user_id == user_id))
                connection.execute(delete(User).where(User.id == user_id))
        engine.dispose()
