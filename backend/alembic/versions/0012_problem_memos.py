"""Problem memos with resolution timestamps."""

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision = "0012_problem_memos"
down_revision = "0011_weekly_schedules"
branch_labels = None
depends_on = None


def upgrade():
    precise = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
    op.create_table(
        "problems",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_resolved", sa.Boolean(), nullable=False),
        sa.Column("resolved_at", precise),
        sa.Column("revision", sa.String(36), nullable=False),
        sa.Column("created_at", precise, nullable=False),
        sa.Column("updated_at", precise, nullable=False),
        sa.CheckConstraint(
            "(is_resolved = 0 AND resolved_at IS NULL) OR "
            "(is_resolved = 1 AND resolved_at IS NOT NULL)",
            name="problem_resolution",
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(
        "ix_problems_user_status_created",
        "problems",
        ["user_id", "is_resolved", "created_at", "id"],
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM problems")):
        raise RuntimeError("Export and remove problem memos before downgrading")
    op.drop_index("ix_problems_user_status_created", table_name="problems")
    op.drop_table("problems")
