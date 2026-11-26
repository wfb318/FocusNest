"""Allow each note to use ordinary or encrypted cloud storage."""

import sqlalchemy as sa

from alembic import op

revision = "0014_note_encryption"
down_revision = "0013_note_problem_link"
branch_labels = None
depends_on = None

PAYLOAD_CHECK = (
    "(storage_mode = 'cloud' AND title IS NOT NULL AND content IS NOT NULL "
    "AND encrypted_payload IS NULL AND content_revision IS NULL) OR "
    "(storage_mode = 'cloud_encrypted' AND title IS NULL AND content IS NULL "
    "AND encrypted_payload IS NOT NULL AND content_revision IS NOT NULL)"
)


def upgrade() -> None:
    # Apply the MySQL schema change as a single ALTER TABLE.
    op.execute(
        "ALTER TABLE notes "
        "ADD COLUMN storage_mode VARCHAR(24) NOT NULL DEFAULT 'cloud', "
        "ADD COLUMN encrypted_payload MEDIUMTEXT NULL, "
        "ADD COLUMN content_revision VARCHAR(36) NULL, "
        "MODIFY COLUMN title VARCHAR(200) NULL, "
        "MODIFY COLUMN content MEDIUMTEXT NULL, "
        f"ADD CONSTRAINT ck_notes_storage_payload CHECK ({PAYLOAD_CHECK})"
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT 1 FROM notes WHERE storage_mode <> 'cloud' LIMIT 1")):
        raise RuntimeError("Convert encrypted notes explicitly before downgrading")
    op.execute(
        "ALTER TABLE notes "
        "DROP CHECK ck_notes_storage_payload, "
        "MODIFY COLUMN title VARCHAR(200) NOT NULL, "
        "MODIFY COLUMN content MEDIUMTEXT NOT NULL, "
        "DROP COLUMN content_revision, "
        "DROP COLUMN encrypted_payload, "
        "DROP COLUMN storage_mode"
    )
