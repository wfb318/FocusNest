import json
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.content_crypto import ContentContext, get_content_crypto, invalid_ciphertext
from app.core.exceptions import AppError
from app.models.note import Note
from app.models.problem import Problem
from app.models.user import User, utcnow
from app.repositories import notes as repository
from app.schemas.note import (
    NoteBody,
    NoteCreate,
    NotePage,
    NoteRead,
    NoteStorageChange,
    NoteSummary,
    NoteUpdate,
)
from app.services import note_folders as folders


def check_problem(db: Session, user: User, problem_id: str | None) -> None:
    if (
        problem_id
        and db.scalar(
            select(Problem.id)
            .where(Problem.id == problem_id, Problem.user_id == user.id)
            .with_for_update()
        )
        is None
    ):
        raise AppError(404, 40408, "Problem not found")


def owned(db: Session, user: User, note_id: str, *, lock: bool = False) -> Note:
    note = repository.find_owned(db, user.id, note_id, lock=lock)
    if note is None:
        raise AppError(404, 40404, "Note not found")
    return note


def get_note(db: Session, user: User, note_id: str) -> NoteRead:
    return read_note(owned(db, user, note_id))


def content_context(note: Note, revision: str) -> ContentContext:
    return ContentContext(note.user_id, "note", note.id, "payload", revision)


def read_body(note: Note) -> tuple[str, str]:
    if note.storage_mode == "cloud" and note.title is not None and note.content is not None:
        return note.title, note.content
    if (
        note.storage_mode != "cloud_encrypted"
        or not note.encrypted_payload
        or not note.content_revision
    ):
        raise invalid_ciphertext()
    payload = get_content_crypto().decrypt(
        note.encrypted_payload, content_context(note, note.content_revision)
    )
    try:
        body = NoteBody.model_validate_json(payload, strict=True)
    except ValidationError:
        raise invalid_ciphertext() from None
    return body.title, body.content


def read_note(note: Note) -> NoteRead:
    title, content = read_body(note)
    metadata = {name: getattr(note, name) for name in NoteSummary.model_fields if name != "title"}
    return NoteRead(title=title, content=content, **metadata)


def write_body(note: Note, title: str, content: str, mode: str) -> None:
    revision = str(uuid4())
    if mode == "cloud_encrypted":
        payload = json.dumps(
            {"title": title, "content": content}, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        note.encrypted_payload = get_content_crypto().encrypt(
            payload, content_context(note, revision)
        )
        note.content_revision = revision
        note.title = None
        note.content = None
    else:
        note.title = title
        note.content = content
        note.encrypted_payload = None
        note.content_revision = None
    note.storage_mode = mode
    note.revision = revision
    note.updated_at = utcnow()


def list_notes(db: Session, user: User, **filters) -> NotePage:
    if filters.get("folder_id"):
        folders.owned(db, user, filters["folder_id"])
    if filters.get("folder_id") and filters.get("unfiled"):
        raise AppError(422, 42200, "Conflicting folder filters")
    items, total = repository.list_owned(db, user.id, **filters)
    return NotePage(
        items=[NoteSummary.model_validate(item) for item in items],
        total=total,
        page=filters["page"],
        page_size=filters["page_size"],
    )


def flush_and_verify(db: Session, note: Note, expected_body: tuple[str, str]) -> NoteRead:
    mode = note.storage_mode
    db.flush()
    db.refresh(note)
    result = read_note(note)
    if result.storage_mode != mode or (result.title, result.content) != expected_body:
        raise invalid_ciphertext()
    return result


def persist(db: Session, note: Note, expected_body: tuple[str, str]) -> NoteRead:
    result = flush_and_verify(db, note, expected_body)
    db.commit()
    return result


def create(db: Session, user: User, payload: NoteCreate) -> NoteRead:
    folders.lock_user(db, user.id)
    check_problem(db, user, payload.problem_id)
    if payload.folder_id:
        folders.owned(db, user, payload.folder_id)
    note = Note(
        id=str(uuid4()),
        user_id=user.id,
        pinned=payload.pinned,
        folder_id=payload.folder_id,
        problem_id=payload.problem_id,
    )
    write_body(note, payload.title, payload.content, payload.storage_mode)
    db.add(note)
    return persist(db, note, (payload.title, payload.content))


def check_revision(note: Note, revision: str) -> None:
    if note.revision != revision:
        raise AppError(409, 40904, "Note changed; reload before saving")


def update(db: Session, user: User, note_id: str, payload: NoteUpdate) -> NoteRead:
    folders.lock_user(db, user.id)
    note = owned(db, user, note_id, lock=True)
    check_revision(note, payload.expected_revision)
    if "storage_mode" in payload.model_fields_set and payload.storage_mode != note.storage_mode:
        raise AppError(409, 40932, "Use the dedicated storage change operation")
    if note.storage_mode == "cloud_encrypted":
        read_body(note)
    if "problem_id" in payload.model_fields_set:
        check_problem(db, user, payload.problem_id)
        note.problem_id = payload.problem_id
    if "folder_id" in payload.model_fields_set:
        if payload.folder_id:
            folders.owned(db, user, payload.folder_id)
        note.folder_id = payload.folder_id
    note.pinned = payload.pinned
    write_body(note, payload.title, payload.content, note.storage_mode)
    return persist(db, note, (payload.title, payload.content))


def stage_storage_change(
    db: Session, user: User, note_id: str, payload: NoteStorageChange
) -> NoteRead:
    folders.lock_user(db, user.id)
    note = owned(db, user, note_id, lock=True)
    check_revision(note, payload.expected_revision)
    if note.storage_mode == payload.storage_mode:
        return read_note(note)
    title, content = read_body(note)
    write_body(note, title, content, payload.storage_mode)
    return flush_and_verify(db, note, (title, content))


def change_storage(db: Session, user: User, note_id: str, payload: NoteStorageChange) -> NoteRead:
    result = stage_storage_change(db, user, note_id, payload)
    db.commit()
    return result


def delete_note(db: Session, user: User, note_id: str, revision: str) -> None:
    folders.lock_user(db, user.id)
    note = owned(db, user, note_id, lock=True)
    check_revision(note, revision)
    db.delete(note)
    db.commit()
