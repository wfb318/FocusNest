import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models import Document, User
from app.schemas.document import DocumentRename
from app.schemas.user import Registration
from app.services import auth, documents


@pytest.mark.skipif(os.environ.get("FOCUSNEST_TEST_MYSQL") != "1", reason="Requires MySQL")
@pytest.mark.parametrize("delete_race", [False, True])
def test_only_one_stale_document_write_succeeds(delete_race):
    engine = create_engine(get_settings().database_url)
    user_id = None
    try:
        with Session(engine, expire_on_commit=False) as db:
            name = "doc_" + uuid4().hex[:20]
            user = auth.register(
                db,
                Registration(
                    username=name, email=name + "@example.com", password="Temporary-doc-test-739!"
                ),
            )
            user_id = user.id
            document = documents.upload(db, user, "test.txt", b"test")
        barrier = Barrier(2)

        def write(number):
            with Session(engine, expire_on_commit=False) as db:
                user = db.get(User, user_id)
                barrier.wait(timeout=10)
                try:
                    if delete_race and number == 1:
                        documents.delete_document(db, user, document.id, document.revision)
                    else:
                        documents.rename(
                            db,
                            user,
                            document.id,
                            DocumentRename(title=str(number), expected_revision=document.revision),
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
                connection.execute(delete(Document).where(Document.user_id == user_id))
                connection.execute(delete(User).where(User.id == user_id))
        engine.dispose()
