import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.models import AuthSession, User
from app.schemas.auth import Login
from app.schemas.user import Registration
from app.services import auth


@pytest.mark.skipif(
    os.environ.get("FOCUSNEST_TEST_MYSQL") != "1", reason="Requires real MySQL concurrency"
)
def test_only_one_concurrent_refresh_succeeds():
    engine = create_engine(get_settings().database_url)
    user_id = None
    name = "race_" + uuid4().hex[:20]
    try:
        with Session(engine, expire_on_commit=False) as db:
            user = auth.register(
                db,
                Registration(
                    username=name,
                    email=name + "@example.com",
                    password="Temporary-test-823!",
                ),
            )
            user_id = user.id
            _, token = auth.login(db, Login(username=name, password="Temporary-test-823!"))

        def refresh_once():
            with Session(engine, expire_on_commit=False) as db:
                try:
                    auth.refresh(db, token)
                    return 200
                except AppError as error:
                    return error.status_code

        with ThreadPoolExecutor(max_workers=2) as workers:
            futures = [workers.submit(refresh_once) for _ in range(2)]
            assert sorted(f.result(timeout=15) for f in futures) == [200, 401]
    finally:
        if user_id is not None:
            with engine.begin() as connection:
                connection.execute(delete(AuthSession).where(AuthSession.user_id == user_id))
                connection.execute(delete(User).where(User.id == user_id))
        engine.dispose()
