"""Add mutually exclusive plaintext and encrypted document storage."""

import sqlalchemy as sa

from alembic import op

revision = "0016_document_encryption"
down_revision = "0015_encrypted_journals"
branch_labels = None
depends_on = None

PAYLOAD_CHECK = (
    "(storage_mode = 'cloud' AND title IS NOT NULL AND filename IS NOT NULL "
    "AND raw_content IS NOT NULL AND encrypted_file IS NULL AND encrypted_metadata IS NULL) OR "
    "(storage_mode = 'cloud_encrypted' AND title IS NULL AND filename IS NULL "
    "AND raw_content IS NULL AND preview_data IS NULL "
    "AND encrypted_file IS NOT NULL AND encrypted_metadata IS NOT NULL)"
)


def upgrade() -> None:
    op.execute(
        "ALTER TABLE documents "
        "ADD COLUMN storage_mode VARCHAR(24) NOT NULL DEFAULT 'cloud', "
        "ADD COLUMN encrypted_file MEDIUMTEXT NULL, "
        "ADD COLUMN encrypted_metadata MEDIUMTEXT NULL, "
        "MODIFY COLUMN title VARCHAR(200) NULL, "
        "MODIFY COLUMN filename VARCHAR(255) NULL, "
        "MODIFY COLUMN raw_content MEDIUMBLOB NULL, "
        f"ADD CONSTRAINT ck_documents_storage_payload CHECK ({PAYLOAD_CHECK})"
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT 1 FROM documents WHERE storage_mode <> 'cloud' LIMIT 1")
    ):
        raise RuntimeError("Convert encrypted documents explicitly before downgrading")
    op.execute(
        "ALTER TABLE documents "
        "DROP CHECK ck_documents_storage_payload, "
        "MODIFY COLUMN title VARCHAR(200) NOT NULL, "
        "MODIFY COLUMN filename VARCHAR(255) NOT NULL, "
        "MODIFY COLUMN raw_content MEDIUMBLOB NOT NULL, "
        "DROP COLUMN encrypted_metadata, "
        "DROP COLUMN encrypted_file, "
        "DROP COLUMN storage_mode"
    )
