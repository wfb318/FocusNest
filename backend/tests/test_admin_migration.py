import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_role_migration_preserves_existing_users_and_sessions():
    engine = sa.create_engine("sqlite://")

    @sa.event.listens_for(engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    metadata = sa.MetaData()
    users = sa.Table(
        "users",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("username", sa.String(32), nullable=False),
    )
    sessions = sa.Table(
        "auth_sessions",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.ForeignKey("users.id", ondelete="CASCADE")),
    )
    metadata.create_all(engine)
    path = Path(__file__).resolve().parents[1] / "alembic/versions/0019_admin_and_presence.py"
    spec = importlib.util.spec_from_file_location("admin_migration_test", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    try:
        with engine.begin() as connection:
            connection.execute(users.insert().values(id="existing-user", username="existing"))
            connection.execute(
                sessions.insert().values(id="existing-session", user_id="existing-user")
            )
            migration.op = Operations(MigrationContext.configure(connection))
            migration.upgrade()
            assert connection.scalar(sa.text("SELECT role FROM users")) == "user"
            assert connection.scalar(sa.text("SELECT COUNT(*) FROM auth_sessions")) == 1
            connection.execute(sa.text("UPDATE users SET role = 'admin'"))
            with pytest.raises(RuntimeError, match="Demote"):
                migration.downgrade()
            connection.execute(sa.text("UPDATE users SET role = 'user'"))
            migration.downgrade()
            assert "role" not in {
                column["name"] for column in sa.inspect(connection).get_columns("users")
            }
            assert connection.scalar(sa.text("SELECT COUNT(*) FROM users")) == 1
            assert connection.scalar(sa.text("SELECT COUNT(*) FROM auth_sessions")) == 1
    finally:
        engine.dispose()
