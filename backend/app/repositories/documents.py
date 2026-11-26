from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, undefer

from app.models.document import Document

summary_title = case((Document.storage_mode == "cloud", Document.title), else_="加密文档").label(
    "title"
)


def find_owned(db: Session, user_id: str, document_id: str, *, lock: bool = False):
    query = (
        select(Document)
        .options(
            undefer(Document.raw_content),
            undefer(Document.encrypted_file),
            undefer(Document.encrypted_metadata),
        )
        .where(Document.user_id == user_id, Document.id == document_id)
    )
    return db.scalar(query.with_for_update() if lock else query)


def list_owned(
    db: Session, user_id: str, *, page: int, page_size: int, q: str | None, kind: str | None
):
    filters = [Document.user_id == user_id]
    if kind:
        filters.append(Document.kind == kind)
    if q:
        filters.append(Document.storage_mode == "cloud")
        filters.append(
            or_(
                Document.title.contains(q, autoescape=True),
                Document.filename.contains(q, autoescape=True),
            )
        )
    total = db.scalar(select(func.count()).select_from(Document).where(*filters)) or 0
    query = select(
        Document.id,
        summary_title,
        case((Document.storage_mode == "cloud", Document.filename), else_="").label("filename"),
        Document.storage_mode,
        Document.kind,
        Document.size_bytes,
        Document.revision,
        Document.created_at,
        Document.updated_at,
    ).where(*filters)
    items = db.execute(
        query.order_by(Document.created_at.desc(), Document.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return items, total
