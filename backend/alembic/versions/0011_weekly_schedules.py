"""Weekly recurrence, occurrence exceptions, and fixed-time focus sessions."""

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import context, op

revision = "0011_weekly_schedules"
down_revision = "0010_document_formats"
branch_labels = None
depends_on = None


def inspector():
    return None if context.is_offline_mode() else sa.inspect(op.get_bind())


def create_table(name, *args, **kwargs):
    # MySQL DDL commits separately. Allow retry after an interrupted upgrade.
    view = inspector()
    if view is None or not view.has_table(name):
        op.create_table(name, *args, **kwargs)


def common_fields():
    return [
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False),
        sa.Column("start_minute", sa.Integer(), nullable=False),
        sa.Column("end_minute", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("tasks.id", ondelete="SET NULL")),
        sa.Column("timer_enabled", sa.Boolean(), nullable=False),
        sa.Column("remind_start", sa.Boolean(), nullable=False),
        sa.Column("remind_end", sa.Boolean(), nullable=False),
    ]


def constraints(up=True):
    view = inspector()
    existing = (
        {item["name"] for item in view.get_check_constraints("focus_sessions")} if view else None
    )
    for name in ("mode", "status", "duration", "active"):
        full_name = f"ck_focus_sessions_focus_{name}"
        if existing is None or full_name in existing:
            op.drop_constraint(op.f(full_name), "focus_sessions", type_="check")
    modes = (
        "'pomodoro','countdown','stopwatch','scheduled'"
        if up
        else "'pomodoro','countdown','stopwatch'"
    )
    active = "'scheduled','running','paused'" if up else "'running','paused'"
    op.create_check_constraint("focus_mode", "focus_sessions", f"mode IN ({modes})")
    op.create_check_constraint(
        "focus_status", "focus_sessions", f"status IN ({active},'completed','cancelled')"
    )
    duration = (
        (
            "(mode IN ('stopwatch','scheduled') AND duration_seconds IS NULL) OR "
            "(mode IN ('pomodoro','countdown') AND duration_seconds BETWEEN 60 AND 86400)"
        )
        if up
        else (
            "(mode = 'stopwatch' AND duration_seconds IS NULL) OR "
            "(mode != 'stopwatch' AND duration_seconds BETWEEN 60 AND 86400)"
        )
    )
    op.create_check_constraint("focus_duration", "focus_sessions", duration)
    op.create_check_constraint(
        "focus_active",
        "focus_sessions",
        f"(status IN ({active}) AND active_user_id IS NOT NULL AND active_user_id=user_id) OR "
        "(status IN ('completed','cancelled') AND active_user_id IS NULL)",
    )


def upgrade():
    create_table(
        "weekly_schedules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        *common_fields(),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_until", sa.Date()),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="schedule_weekday"),
        sa.CheckConstraint(
            "start_minute >= 0 AND end_minute <= 1440 AND start_minute < end_minute",
            name="schedule_times",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    view = inspector()
    if view is None or not any(
        item["name"] == "ix_schedule_user_dates" for item in view.get_indexes("weekly_schedules")
    ):
        op.create_index(
            "ix_schedule_user_dates",
            "weekly_schedules",
            ["user_id", "effective_from", "effective_until"],
        )
    create_table(
        "schedule_exceptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "schedule_id",
            sa.String(36),
            sa.ForeignKey("weekly_schedules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("occurrence_date", sa.Date(), nullable=False),
        sa.Column("skipped", sa.Boolean(), nullable=False),
        *common_fields(),
        sa.UniqueConstraint("schedule_id", "occurrence_date", name="uq_schedule_exception_date"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    precise = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
    columns = [
        sa.Column("title", sa.String(200), nullable=False, server_default=""),
        sa.Column("window_start", precise),
        sa.Column("window_end", precise),
        sa.Column("occurrence_key", sa.String(48)),
    ]
    view = inspector()
    existing = {item["name"] for item in view.get_columns("focus_sessions")} if view else set()
    for column in columns:
        if column.name not in existing:
            op.add_column("focus_sessions", column)
    if view is None or not any(
        item["name"] == "uq_focus_sessions_occurrence_key"
        for item in view.get_unique_constraints("focus_sessions")
    ):
        op.create_unique_constraint(
            "uq_focus_sessions_occurrence_key", "focus_sessions", ["occurrence_key"]
        )
    constraints()


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM focus_sessions WHERE mode='scheduled'")):
        raise RuntimeError("Fixed-time records must be exported/removed before downgrading")
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM weekly_schedules")):
        raise RuntimeError("Weekly plans must be exported/removed before downgrading")
    constraints(False)
    op.drop_constraint("uq_focus_sessions_occurrence_key", "focus_sessions", type_="unique")
    for name in ("occurrence_key", "window_end", "window_start", "title"):
        op.drop_column("focus_sessions", name)
    op.drop_table("schedule_exceptions")
    op.drop_index("ix_schedule_user_dates", table_name="weekly_schedules")
    op.drop_table("weekly_schedules")
