"""Add application administrator roles and authenticated session presence."""

import sqlalchemy as sa

from alembic import op

revision = "0019_admin_and_presence"
down_revision = "0018_schedule_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        # Rebuilding users can cascade-delete its children with foreign keys on.
        op.add_column(
            "users",
            sa.Column(
                "role",
                sa.String(16),
                sa.CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
                nullable=False,
                server_default="user",
            ),
        )
    else:
        op.add_column(
            "users", sa.Column("role", sa.String(16), nullable=False, server_default="user")
        )
        op.create_check_constraint("ck_users_role", "users", "role IN ('user', 'admin')")
    op.add_column("auth_sessions", sa.Column("last_seen_at", sa.DateTime(), nullable=True))
    op.create_index("ix_auth_sessions_last_seen_at", "auth_sessions", ["last_seen_at"])


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT 1 FROM users WHERE role = 'admin' LIMIT 1")):
        raise RuntimeError("Demote administrator accounts before downgrading")
    op.drop_index("ix_auth_sessions_last_seen_at", table_name="auth_sessions")
    op.drop_column("auth_sessions", "last_seen_at")
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("ck_users_role", "users", type_="check")
    op.drop_column("users", "role")
