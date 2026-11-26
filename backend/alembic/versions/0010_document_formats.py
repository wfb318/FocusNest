"""PDF and Office preview metadata; originals remain unchanged."""

import sqlalchemy as sa

from alembic import op

revision = "0010_document_formats"
down_revision = "0009_documents"
branch_labels = None
depends_on = None


def upgrade():
    op.drop_constraint("ck_documents_kind", "documents", type_="check")
    op.drop_constraint("ck_documents_size", "documents", type_="check")
    op.create_check_constraint(
        "ck_documents_kind",
        "documents",
        "kind IN ('markdown','text','pdf','word','presentation','spreadsheet')",
    )
    op.create_check_constraint(
        "ck_documents_size", "documents", "size_bytes > 0 AND size_bytes <= 10485760"
    )
    op.add_column("documents", sa.Column("preview_data", sa.JSON(), nullable=True))


def downgrade():
    # Refuse to remove format support while such originals are still stored.
    count = op.get_bind().scalar(
        sa.text(
            "SELECT COUNT(*) FROM documents "
            "WHERE kind NOT IN ('markdown','text') OR size_bytes > 524288"
        )
    )
    if count:
        raise RuntimeError("Remove new-format documents before downgrading")
    op.drop_column("documents", "preview_data")
    op.drop_constraint("ck_documents_kind", "documents", type_="check")
    op.drop_constraint("ck_documents_size", "documents", type_="check")
    op.create_check_constraint("ck_documents_kind", "documents", "kind IN ('markdown','text')")
    op.create_check_constraint(
        "ck_documents_size", "documents", "size_bytes > 0 AND size_bytes <= 524288"
    )
