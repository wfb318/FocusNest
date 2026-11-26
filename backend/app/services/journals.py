import hashlib
import hmac
import json
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.user import User
from app.repositories import journals as repository
from app.schemas.journal import (
    JournalDay,
    JournalMigrationCleanup,
    JournalPage,
    JournalRead,
    JournalSave,
    JournalSummary,
)


def today(user: User) -> date:
    return datetime.now(timezone.utc).astimezone(ZoneInfo(user.timezone)).date()


def valid_date(value: date) -> None:
    if value.year < 1000:
        raise AppError(422, 42200, "Date must be between 1000 and 9999")


def get_day(db: Session, user: User, entry_date: date) -> JournalDay:
    valid_date(entry_date)
    entry = repository.find_day(db, user.id, entry_date)
    return JournalDay(
        entry_date=entry_date, entry=JournalRead.model_validate(entry) if entry else None
    )


def list_entries(db: Session, user: User, **filters) -> JournalPage:
    for name in ("start_date", "end_date"):
        if filters[name]:
            valid_date(filters[name])
    if filters["start_date"] and filters["end_date"]:
        if filters["start_date"] > filters["end_date"]:
            raise AppError(422, 42200, "Invalid date range")
    items, total = repository.list_owned(db, user.id, **filters)
    return JournalPage(
        items=[JournalSummary.model_validate(item) for item in items],
        total=total,
        page=filters["page"],
        page_size=filters["page_size"],
    )


def save(db: Session, user: User, entry_date: date, payload: JournalSave) -> JournalRead:
    # All current journal accounts use local storage. Never insert a cloud row here.
    raise AppError(403, 40321, "Cloud journal writes are disabled; save locally")


def delete_entry(db: Session, user: User, entry_date: date, revision: str) -> None:
    raise AppError(403, 40321, "Legacy journal deletion is disabled")


def source_digest(entry: JournalRead) -> str:
    source = entry.model_dump(mode="json")
    snapshot = {
        key: source[key] for key in ("entry_date", "title", "content", "created_at", "updated_at")
    }
    raw = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def cleanup_migrated_copy(
    db: Session, user: User, entry_date: date, payload: JournalMigrationCleanup
) -> dict[str, bool]:
    valid_date(entry_date)
    repository.lock_user(db, user.id)
    entry = repository.find_day(db, user.id, entry_date, lock=True)
    if entry is None:
        return {"removed": True, "already_missing": True}
    if entry.revision != payload.expected_revision or not hmac.compare_digest(
        source_digest(JournalRead.model_validate(entry)), payload.verified_source_digest
    ):
        raise AppError(409, 40922, "Legacy journal changed; verify local and cloud copies again")
    # The server validates ownership/version/source digest, not the user's physical disk.
    # Local read-back and the separate confirmation belong to the client migration flow.
    db.delete(entry)
    db.commit()
    return {"removed": True, "already_missing": False}
