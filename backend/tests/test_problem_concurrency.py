import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models import User
from app.schemas.problem import ProblemCreate, ProblemEdit, ProblemStatus
from app.schemas.user import Registration
from app.services import auth, problems


@pytest.mark.skipif(os.environ.get("FOCUSNEST_TEST_MYSQL") != "1", reason="Requires MySQL locks")
def test_simultaneous_edit_and_resolve_preserve_revision():
    engine = create_engine(get_settings().database_url)
    uid = None
    try:
        with Session(engine, expire_on_commit=False) as db:
            name = "problemrace_" + uuid4().hex[:16]
            user = auth.register(
                db,
                Registration(
                    username=name,
                    email=name + "@example.com",
                    password="Temporary-problem-race-384!",
                ),
            )
            uid = user.id
            item = problems.create(db, user, ProblemCreate(content="Original"))
        barrier = Barrier(2)

        def work(resolve):
            with Session(engine, expire_on_commit=False) as db:
                user = db.get(User, uid)
                barrier.wait(timeout=10)
                payload = (
                    ProblemStatus(is_resolved=True, expected_revision=item.revision)
                    if resolve
                    else ProblemEdit(content="Changed", expected_revision=item.revision)
                )
                try:
                    problems.edit(db, user, item.id, payload)
                    return 200
                except AppError as exc:
                    assert exc.code == 40912
                    return 409

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(work, (True, False)))
        assert sorted(results) == [200, 409]
    finally:
        if uid:
            with engine.begin() as conn:
                conn.execute(delete(User).where(User.id == uid))
        engine.dispose()
