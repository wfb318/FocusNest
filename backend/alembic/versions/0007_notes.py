"""Phase 5: private Markdown notes."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME, MEDIUMTEXT

from alembic import op

revision = "0007_notes"
down_revision = "0006_journals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    precise_time = sa.DateTime().with_variant(DATETIME(fsp=6), "mysql")
    op.create_table(
        "notes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False),
        sa.Column("pinned", sa.Boolean(), nullable=False),
        sa.Column("revision", sa.String(36), nullable=False),
        sa.Column("created_at", precise_time, nullable=False),
        sa.Column("updated_at", precise_time, nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index(
        "ix_notes_user_pinned_updated", "notes", ["user_id", "pinned", "updated_at", "id"]
    )


def downgrade() -> None:
    op.drop_table("notes")
