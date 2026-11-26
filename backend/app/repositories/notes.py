from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.models.note import Note

summary_title = case((Note.storage_mode == "cloud", Note.title), else_="加密笔记").label("title")


def find_owned(db: Session, user_id: str, note_id: str, *, lock: bool = False):
    query = select(Note).where(Note.user_id == user_id, Note.id == note_id)
    return db.scalar(query.with_for_update() if lock else query)


def list_owned(
    db: Session,
    user_id: str,
    *,
    page: int,
    page_size: int,
    q: str | None,
    pinned: bool | None,
    folder_id: str | None = None,
    unfiled: bool = False,
):
    filters = [Note.user_id == user_id]
    if folder_id is not None:
        filters.append(Note.folder_id == folder_id)
    if unfiled:
        filters.append(Note.folder_id.is_(None))
    if pinned is not None:
        filters.append(Note.pinned == pinned)
    if q:
        filters.append(Note.storage_mode == "cloud")
        filters.append(
            or_(Note.title.contains(q, autoescape=True), Note.content.contains(q, autoescape=True))
        )
    total = db.scalar(select(func.count()).select_from(Note).where(*filters)) or 0
    query = select(
        Note.id,
        Note.folder_id,
        Note.problem_id,
        summary_title,
        Note.storage_mode,
        Note.pinned,
        Note.revision,
        Note.created_at,
        Note.updated_at,
    ).where(*filters)
    items = db.execute(
        query.order_by(Note.pinned.desc(), Note.updated_at.desc(), Note.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return items, total
