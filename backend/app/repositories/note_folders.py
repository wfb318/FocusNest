from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.note import Note
from app.models.note_folder import NoteFolder
from app.models.user import User


def lock_user(db: Session, user_id: str):
    db.execute(select(User.id).where(User.id == user_id).with_for_update()).one()


def list_owned(db: Session, user_id: str):
    return db.scalars(
        select(NoteFolder)
        .where(NoteFolder.user_id == user_id)
        .order_by(NoteFolder.name, NoteFolder.id)
    ).all()


def find_owned(db: Session, user_id: str, folder_id: str):
    return db.scalar(
        select(NoteFolder)
        .where(NoteFolder.user_id == user_id, NoteFolder.id == folder_id)
        .with_for_update()
    )


def sibling(db: Session, user_id: str, parent_id: str | None, name: str):
    return db.scalar(
        select(NoteFolder)
        .where(
            NoteFolder.user_id == user_id,
            NoteFolder.parent_id == parent_id,
            NoteFolder.name == name,
        )
        .with_for_update()
    )


def has_children(db: Session, user_id: str, folder_id: str):
    return (
        db.scalar(
            select(NoteFolder.id)
            .where(NoteFolder.user_id == user_id, NoteFolder.parent_id == folder_id)
            .limit(1)
            .with_for_update()
        )
        is not None
    )


def contained_notes(db: Session, user_id: str, folder_id: str):
    return db.scalars(
        select(Note).where(Note.user_id == user_id, Note.folder_id == folder_id).with_for_update()
    ).all()
