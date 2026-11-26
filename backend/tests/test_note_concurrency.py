import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models import Note, User
from app.schemas.note import NoteCreate, NoteUpdate
from app.schemas.user import Registration
from app.services import auth, notes


@pytest.mark.skipif(os.environ.get("FOCUSNEST_TEST_MYSQL") != "1", reason="Requires MySQL")
@pytest.mark.parametrize("race_delete", [False, True])
def test_stale_concurrent_writers_cannot_both_succeed(race_delete):
    engine = create_engine(get_settings().database_url)
    user_id = None
    try:
        with Session(engine, expire_on_commit=False) as db:
            name = "note_" + uuid4().hex[:18]
            user = auth.register(
                db,
                Registration(
                    username=name, email=name + "@example.com", password="Temporary-note-739!"
                ),
            )
            user_id = user.id
            note = notes.create(db, user, NoteCreate(title="并发", content="initial"))
        barrier = Barrier(2)

        def write(number):
            with Session(engine, expire_on_commit=False) as db:
                user = db.get(User, user_id)
                barrier.wait(timeout=10)
                try:
                    if race_delete and number == 1:
                        notes.delete_note(db, user, note.id, note.revision)
                    else:
                        notes.update(
                            db,
                            user,
                            note.id,
                            NoteUpdate(
                                title="并发", content=str(number), expected_revision=note.revision
                            ),
                        )
                    return True
                except AppError as exc:
                    assert exc.status_code in (404, 409)
                    return False

        with ThreadPoolExecutor(max_workers=2) as workers:
            assert sorted(workers.map(write, range(2))) == [False, True]
    finally:
        if user_id:
            with engine.begin() as connection:
                connection.execute(delete(Note).where(Note.user_id == user_id))
                connection.execute(delete(User).where(User.id == user_id))
        engine.dispose()
