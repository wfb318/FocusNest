from datetime import date
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import func, literal, select
from sqlalchemy.orm import Session

from app.core.content_crypto import ContentContext, get_content_crypto, invalid_ciphertext
from app.core.exceptions import AppError
from app.models.journal import EncryptedJournal
from app.models.user import User, utcnow
from app.repositories.journals import lock_user
from app.schemas.journal import (
    EncryptedJournalBody,
    JournalDay,
    JournalPage,
    JournalRead,
    JournalSave,
    JournalSummary,
)
from app.services.journals import valid_date


def find(db: Session, user: User, day: date, *, lock: bool = False) -> EncryptedJournal | None:
    valid_date(day)
    query = select(EncryptedJournal).where(
        EncryptedJournal.user_id == user.id, EncryptedJournal.entry_date == day
    )
    return db.scalar(query.with_for_update() if lock else query)


def context(entry: EncryptedJournal) -> ContentContext:
    return ContentContext(entry.user_id, "journal", entry.id, "payload", entry.revision)


def read(entry: EncryptedJournal) -> JournalRead:
    data = get_content_crypto().decrypt(entry.encrypted_payload, context(entry))
    try:
        body = EncryptedJournalBody.model_validate_json(data)
    except ValidationError:
        raise invalid_ciphertext() from None
    if body.entry_date != entry.entry_date:
        raise invalid_ciphertext()
    return JournalRead(
        id=entry.id,
        revision=entry.revision,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
        **body.model_dump(),
    )


def get_day(db: Session, user: User, day: date) -> JournalDay:
    entry = find(db, user, day)
    return JournalDay(entry_date=day, entry=read(entry) if entry else None)


def list_entries(
    db: Session,
    user: User,
    page: int,
    page_size: int,
    start_date: date | None,
    end_date: date | None,
) -> JournalPage:
    filters = [EncryptedJournal.user_id == user.id]
    if start_date:
        valid_date(start_date)
        filters.append(EncryptedJournal.entry_date >= start_date)
    if end_date:
        valid_date(end_date)
        filters.append(EncryptedJournal.entry_date <= end_date)
    if start_date and end_date and start_date > end_date:
        raise AppError(422, 42200, "Invalid date range")
    total = db.scalar(select(func.count()).select_from(EncryptedJournal).where(*filters)) or 0
    query = (
        select(
            EncryptedJournal.id,
            EncryptedJournal.entry_date,
            literal("加密日记").label("title"),
            EncryptedJournal.revision,
            EncryptedJournal.created_at,
            EncryptedJournal.updated_at,
        )
        .where(*filters)
        .order_by(EncryptedJournal.entry_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return JournalPage(
        items=[JournalSummary.model_validate(row) for row in db.execute(query)],
        total=total,
        page=page,
        page_size=page_size,
    )


def write_and_verify(
    db: Session, entry: EncryptedJournal, body: EncryptedJournalBody
) -> JournalRead:
    entry.revision = str(uuid4())
    entry.encrypted_payload = get_content_crypto().encrypt(
        body.model_dump_json().encode("utf-8"), context(entry)
    )
    db.flush()
    db.refresh(entry)
    result = read(entry)
    if (result.entry_date, result.title, result.content) != (
        body.entry_date,
        body.title,
        body.content,
    ):
        raise invalid_ciphertext()
    return result


def save(db: Session, user: User, day: date, payload: JournalSave) -> JournalRead:
    lock_user(db, user.id)
    entry = find(db, user, day, lock=True)
    if (entry.revision if entry else None) != payload.expected_revision:
        raise AppError(409, 40903, "Encrypted journal changed or already exists")
    if entry is None:
        entry = EncryptedJournal(id=str(uuid4()), user_id=user.id, entry_date=day)
        db.add(entry)
    else:
        read(entry)
    entry.updated_at = utcnow()
    body = EncryptedJournalBody(entry_date=day, title=payload.title, content=payload.content)
    result = write_and_verify(db, entry, body)
    db.commit()
    return result


def delete(db: Session, user: User, day: date, revision: str) -> None:
    lock_user(db, user.id)
    entry = find(db, user, day, lock=True)
    if entry is None:
        raise AppError(404, 40403, "Encrypted journal not found")
    if entry.revision != revision:
        raise AppError(409, 40903, "Encrypted journal changed")
    db.delete(entry)
    db.commit()
