"""Phase 2: user-owned tasks."""

import sqlalchemy as sa

from alembic import op

revision = "0003_tasks"
down_revision = "0002_users_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False),
        sa.Column("scheduled_date", sa.Date()),
        sa.Column("due_date", sa.Date()),
        sa.Column("estimated_minutes", sa.Integer()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('todo', 'doing', 'done')", name="task_status"),
        sa.CheckConstraint("priority IN ('low', 'medium', 'high')", name="task_priority"),
        sa.CheckConstraint(
            "estimated_minutes IS NULL OR estimated_minutes BETWEEN 1 AND 10080",
            name="task_estimate",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_tasks_user_created", "tasks", ["user_id", "created_at", "id"])
    op.create_index("ix_tasks_user_scheduled", "tasks", ["user_id", "scheduled_date"])
    op.create_index("ix_tasks_user_due", "tasks", ["user_id", "due_date"])


def downgrade() -> None:
    op.drop_table("tasks")
