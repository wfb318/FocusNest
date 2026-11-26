"""Preserve fractional seconds across MySQL pause/resume cycles."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

from alembic import op

revision = "0005_focus_timer_precision"
down_revision = "0004_focus_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in ("started_at", "segment_started_at", "ended_at", "updated_at"):
        op.alter_column(
            "focus_sessions",
            column,
            existing_type=sa.DateTime(),
            type_=sa.DateTime().with_variant(DATETIME(fsp=6), "mysql"),
            existing_nullable=column in ("segment_started_at", "ended_at"),
        )
    op.alter_column(
        "focus_sessions",
        "elapsed_seconds",
        existing_type=sa.Float(),
        type_=sa.Double(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "focus_sessions",
        "elapsed_seconds",
        existing_type=sa.Double(),
        type_=sa.Float(),
        existing_nullable=False,
    )
    for column in ("started_at", "segment_started_at", "ended_at", "updated_at"):
        op.alter_column(
            "focus_sessions",
            column,
            existing_type=sa.DateTime().with_variant(DATETIME(fsp=6), "mysql"),
            type_=sa.DateTime(),
            existing_nullable=column in ("segment_started_at", "ended_at"),
        )
