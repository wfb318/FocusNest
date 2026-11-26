"""Record verified, selected content migrations."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

from alembic import op

revision = "0017_content_migration_receipts"
down_revision = "0016_document_encryption"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "content_migration_receipts",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("kind", sa.String(16), primary_key=True),
        sa.Column("source_id", sa.String(36), primary_key=True),
        sa.Column("source_revision", sa.String(36), primary_key=True),
        sa.Column("target_revision", sa.String(36), nullable=False),
        sa.Column(
            "completed_at", sa.DateTime().with_variant(DATETIME(fsp=6), "mysql"), nullable=False
        ),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT 1 FROM content_migration_receipts LIMIT 1")):
        raise RuntimeError("Cannot downgrade while migration receipts exist")
    op.drop_table("content_migration_receipts")
