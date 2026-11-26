from uuid import uuid4

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.note_folder import NoteFolder
from app.models.user import User, utcnow
from app.repositories import note_folders as repository
from app.schemas.note_folder import FolderCreate, FolderRead, FolderRename

lock_user = repository.lock_user


def owned(db: Session, user: User, folder_id: str) -> NoteFolder:
    folder = repository.find_owned(db, user.id, folder_id)
    if folder is None:
        raise AppError(404, 40405, "Folder not found")
    return folder


def list_folders(db: Session, user: User):
    return [FolderRead.model_validate(item) for item in repository.list_owned(db, user.id)]


def unique_name(db: Session, user: User, parent_id: str | None, name: str, exclude=None):
    match = repository.sibling(db, user.id, parent_id, name)
    if match and match.id != exclude:
        raise AppError(409, 40905, "Folder name already exists here")


def check_revision(folder: NoteFolder, revision: str):
    if folder.revision != revision:
        raise AppError(409, 40906, "Folder changed; reload first")


def create(db: Session, user: User, payload: FolderCreate):
    lock_user(db, user.id)
    if payload.parent_id:
        owned(db, user, payload.parent_id)
    unique_name(db, user, payload.parent_id, payload.name)
    folder = NoteFolder(user_id=user.id, **payload.model_dump())
    db.add(folder)
    db.flush()
    result = FolderRead.model_validate(folder)
    db.commit()
    return result


def rename(db: Session, user: User, folder_id: str, payload: FolderRename):
    lock_user(db, user.id)
    folder = owned(db, user, folder_id)
    check_revision(folder, payload.expected_revision)
    unique_name(db, user, folder.parent_id, payload.name, folder.id)
    folder.name = payload.name
    folder.revision = str(uuid4())
    db.flush()
    result = FolderRead.model_validate(folder)
    db.commit()
    return result


def delete_folder(db: Session, user: User, folder_id: str, revision: str):
    lock_user(db, user.id)
    folder = owned(db, user, folder_id)
    check_revision(folder, revision)
    if repository.has_children(db, user.id, folder_id):
        raise AppError(409, 40907, "Remove child folders first")
    # Explicitly bump versions so open editors cannot silently undo the move.
    for note in repository.contained_notes(db, user.id, folder_id):
        note.folder_id = None
        note.revision = str(uuid4())
        note.updated_at = utcnow()
    db.flush()
    db.delete(folder)
    db.commit()
