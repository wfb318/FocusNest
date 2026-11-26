import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models import NoteFolder, User
from app.schemas.note_folder import FolderCreate
from app.schemas.user import Registration
from app.services import auth, note_folders


@pytest.mark.skipif(os.environ.get("FOCUSNEST_TEST_MYSQL") != "1", reason="Requires MySQL")
def test_concurrent_sibling_creation_has_one_winner():
    engine = create_engine(get_settings().database_url)
    user_id = None
    try:
        with Session(engine, expire_on_commit=False) as db:
            name = "folder_" + uuid4().hex[:18]
            user = auth.register(
                db,
                Registration(
                    username=name,
                    email=name + "@example.com",
                    password="Temporary-folder-test-739!",
                ),
            )
            user_id = user.id
        barrier = Barrier(2)

        def create(_):
            with Session(engine) as db:
                user = db.get(User, user_id)
                barrier.wait(timeout=10)
                try:
                    note_folders.create(db, user, FolderCreate(name="Same name"))
                    return True
                except AppError as exc:
                    assert exc.code == 40905
                    return False

        with ThreadPoolExecutor(max_workers=2) as workers:
            assert sorted(workers.map(create, range(2))) == [False, True]
    finally:
        if user_id:
            with engine.begin() as connection:
                connection.execute(delete(NoteFolder).where(NoteFolder.user_id == user_id))
                connection.execute(delete(User).where(User.id == user_id))
        engine.dispose()
