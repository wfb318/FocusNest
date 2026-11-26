"""Selected migration and read-only recovery checks for operators."""

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import literal, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models import Document, EncryptedJournal, Journal, MigrationReceipt, Note, User
from app.schemas.document import DocumentStorageChange
from app.schemas.journal import EncryptedJournalBody
from app.schemas.note import NoteStorageChange
from app.services import documents, encrypted_journals, notes

SourceKind = Literal["note", "document", "journal"]
StoredKind = Literal["note", "document", "journal", "encrypted_journal"]
SOURCE_MODELS = {"note": Note, "document": Document, "journal": Journal}
STORED_MODELS = {**SOURCE_MODELS, "encrypted_journal": EncryptedJournal}
MAX_BATCH = 100


class MigrationItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: SourceKind
    id: UUID
    revision: UUID


class MigrationSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_id: UUID
    items: list[MigrationItem] = Field(min_length=1, max_length=MAX_BATCH)

    @model_validator(mode="after")
    def unique_sources(self):
        keys = {(item.kind, item.id) for item in self.items}
        if len(keys) != len(self.items):
            raise ValueError("A record can be selected only once")
        return self


class CatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    kind: StoredKind
    account_id: UUID
    id: UUID
    revision: UUID
    mode: Literal["cloud", "cloud_encrypted"]
    entry_date: date | None


class RestoreCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1]
    items: list[CatalogEntry]

    @model_validator(mode="after")
    def unique_entries(self):
        if len({(item.kind, item.id) for item in self.items}) != len(self.items):
            raise ValueError("Duplicate catalog record")
        return self


def source_summary(db: Session, account_id: str, kind: SourceKind, after: str | None):
    model = SOURCE_MODELS[kind]
    mode = literal("cloud") if kind == "journal" else model.storage_mode
    columns = [model.id, model.revision, mode.label("mode"), model.updated_at]
    if kind == "journal":
        columns.append(Journal.entry_date)
    query = select(*columns).where(model.user_id == account_id)
    if after:
        query = query.where(model.id > after)
    return [dict(row) for row in db.execute(query.order_by(model.id).limit(MAX_BATCH)).mappings()]


def make_selection(
    db: Session, account_id: UUID, kind: SourceKind, ids: list[UUID]
) -> MigrationSelection:
    model = SOURCE_MODELS[kind]
    rows = db.execute(
        select(model.id, model.revision)
        .where(model.user_id == str(account_id), model.id.in_([str(value) for value in ids]))
        .order_by(model.id)
    ).all()
    if len(rows) != len(ids):
        raise AppError(404, 40433, "One or more selected records do not exist for this account")
    return MigrationSelection(
        account_id=account_id,
        items=[MigrationItem(kind=kind, id=row.id, revision=row.revision) for row in rows],
    )


def migrate_legacy_journal(db: Session, user: User, item: MigrationItem) -> str:
    entry = db.scalar(
        select(Journal)
        .where(Journal.user_id == user.id, Journal.id == str(item.id))
        .with_for_update()
    )
    if entry is None:
        raise AppError(404, 40403, "Legacy journal not found")
    if entry.revision != str(item.revision):
        raise AppError(409, 40922, "Legacy journal changed")
    if encrypted_journals.find(db, user, entry.entry_date, lock=True) is not None:
        raise AppError(409, 40903, "An encrypted journal already exists for this day")
    try:
        body = EncryptedJournalBody(
            entry_date=entry.entry_date, title=entry.title, content=entry.content
        )
    except ValidationError:
        raise AppError(
            422, 42200, "Legacy journal does not meet current content constraints"
        ) from None
    target = EncryptedJournal(
        id=entry.id,
        user_id=entry.user_id,
        entry_date=entry.entry_date,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )
    db.add(target)
    result = encrypted_journals.write_and_verify(db, target, body)
    db.delete(entry)
    return result.revision


def migrate_item(db: Session, account_id: UUID, item: MigrationItem) -> dict:
    """Stage one verified migration and its receipt in the caller's transaction."""
    user = db.scalar(select(User).where(User.id == str(account_id)).with_for_update())
    if user is None:
        raise AppError(404, 40433, "Account not found")
    key = (user.id, item.kind, str(item.id), str(item.revision))
    receipt = db.get(MigrationReceipt, key, with_for_update=True)
    if receipt:
        return {"status": "already_applied", "target_revision": receipt.target_revision}

    if item.kind == "note":
        target_revision = notes.stage_storage_change(
            db,
            user,
            str(item.id),
            NoteStorageChange(storage_mode="cloud_encrypted", expected_revision=str(item.revision)),
        ).revision
    elif item.kind == "document":
        target_revision = documents.stage_storage_change(
            db,
            user,
            str(item.id),
            DocumentStorageChange(
                storage_mode="cloud_encrypted", expected_revision=str(item.revision)
            ),
        ).revision
    else:
        target_revision = migrate_legacy_journal(db, user, item)

    if target_revision == str(item.revision):
        return {"status": "already_encrypted", "target_revision": target_revision}
    db.add(
        MigrationReceipt(
            user_id=user.id,
            kind=item.kind,
            source_id=str(item.id),
            source_revision=str(item.revision),
            target_revision=target_revision,
        )
    )
    return {"status": "migrated", "target_revision": target_revision}


def restore_catalog(db: Session) -> RestoreCatalog:
    items = []
    for kind, model in STORED_MODELS.items():
        if kind in ("note", "document"):
            mode = model.storage_mode
            entry_date = literal(None)
        else:
            mode = literal("cloud" if kind == "journal" else "cloud_encrypted")
            entry_date = model.entry_date
        query = select(model.user_id, model.id, model.revision, mode, entry_date).order_by(model.id)
        items.extend(
            CatalogEntry(
                kind=kind,
                account_id=owner,
                id=item,
                revision=revision,
                mode=storage_mode,
                entry_date=journal_date,
            )
            for owner, item, revision, storage_mode, journal_date in db.execute(query)
        )
    return RestoreCatalog(version=1, items=items)


def verify_restored_item(db: Session, item: CatalogEntry) -> None:
    row = db.get(STORED_MODELS[item.kind], str(item.id))
    if row is None or row.user_id != str(item.account_id) or row.revision != str(item.revision):
        raise AppError(409, 40933, "Restored record changed during verification")
    if item.kind in ("note", "document") and row.storage_mode != item.mode:
        raise AppError(409, 40933, "Restored storage mode changed during verification")
    if item.kind == "encrypted_journal" and row.entry_date != item.entry_date:
        raise AppError(409, 40933, "Restored journal date changed during verification")
    if item.kind == "note":
        notes.read_body(row)
    elif item.kind == "document":
        documents.read_metadata(row)
        documents.read_file(row)
    elif item.kind == "encrypted_journal":
        encrypted_journals.read(row)
    db.expunge(row)
