"""Phase 4: one Markdown journal per user and date."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME, MEDIUMTEXT

from alembic import op

revision = "0006_journals"
down_revision = "0005_focus_timer_precision"
branch_labels = None
depends_on = None


def upgrade() -> None:
    precise_time = sa.DateTime().with_variant(DATETIME(fsp=6), "mysql")
    op.create_table(
        "journals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("revision", sa.String(36), nullable=False),
        sa.Column("created_at", precise_time, nullable=False),
        sa.Column("updated_at", precise_time, nullable=False),
        sa.UniqueConstraint("user_id", "entry_date", name="uq_journals_user_date"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )


def downgrade() -> None:
    op.drop_table("journals")
