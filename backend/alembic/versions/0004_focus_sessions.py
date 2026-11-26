"""Phase 3: persistent focus timers."""

import sqlalchemy as sa

from alembic import op

revision = "0004_focus_sessions"
down_revision = "0003_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "focus_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("active_user_id", sa.String(36), nullable=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id", ondelete="SET NULL")),
        sa.Column("mode", sa.String(16), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("duration_seconds", sa.Integer()),
        sa.Column("elapsed_seconds", sa.Float(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("segment_started_at", sa.DateTime()),
        sa.Column("ended_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("active_user_id", name="uq_focus_sessions_active_user_id"),
        sa.CheckConstraint("mode IN ('pomodoro', 'countdown', 'stopwatch')", name="focus_mode"),
        sa.CheckConstraint("kind IN ('focus', 'break')", name="focus_kind"),
        sa.CheckConstraint(
            "status IN ('running', 'paused', 'completed', 'cancelled')", name="focus_status"
        ),
        sa.CheckConstraint("elapsed_seconds >= 0", name="focus_elapsed"),
        sa.CheckConstraint(
            "(mode = 'stopwatch' AND duration_seconds IS NULL) OR "
            "(mode != 'stopwatch' AND duration_seconds BETWEEN 60 AND 86400)",
            name="focus_duration",
        ),
        sa.CheckConstraint(
            "(status IN ('running', 'paused') AND active_user_id IS NOT NULL "
            "AND active_user_id = user_id) OR "
            "(status IN ('completed', 'cancelled') AND active_user_id IS NULL)",
            name="focus_active",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_focus_user_started", "focus_sessions", ["user_id", "started_at", "id"])


def downgrade() -> None:
    op.drop_table("focus_sessions")
