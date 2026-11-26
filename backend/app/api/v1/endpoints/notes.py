from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DBSession
from app.schemas.common import ApiResponse
from app.schemas.note import NoteCreate, NotePage, NoteRead, NoteStorageChange, NoteUpdate
from app.services import notes

router = APIRouter(prefix="/notes", tags=["notes"])


@router.get("", response_model=ApiResponse[NotePage])
def list_notes(
    user: CurrentUser,
    db: DBSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    q: Annotated[str | None, Query(max_length=100)] = None,
    pinned: bool | None = None,
    folder_id: Annotated[str | None, Query(min_length=36, max_length=36)] = None,
    unfiled: bool = False,
):
    return ApiResponse(
        data=notes.list_notes(
            db,
            user,
            page=page,
            page_size=page_size,
            q=q,
            pinned=pinned,
            folder_id=folder_id,
            unfiled=unfiled,
        )
    )


@router.post("", status_code=201, response_model=ApiResponse[NoteRead])
def create(payload: NoteCreate, user: CurrentUser, db: DBSession):
    return ApiResponse(data=notes.create(db, user, payload))


@router.get("/{note_id}", response_model=ApiResponse[NoteRead])
def get_note(note_id: str, user: CurrentUser, db: DBSession):
    return ApiResponse(data=notes.get_note(db, user, note_id))


@router.put("/{note_id}", response_model=ApiResponse[NoteRead])
def update(note_id: str, payload: NoteUpdate, user: CurrentUser, db: DBSession):
    return ApiResponse(data=notes.update(db, user, note_id, payload))


@router.delete("/{note_id}", response_model=ApiResponse[None])
def delete_note(
    note_id: str,
    revision: Annotated[str, Query(min_length=36, max_length=36)],
    user: CurrentUser,
    db: DBSession,
):
    notes.delete_note(db, user, note_id, revision)
    return ApiResponse(message="Note deleted")


@router.post("/{note_id}/storage", response_model=ApiResponse[NoteRead])
def change_storage(note_id: str, payload: NoteStorageChange, user: CurrentUser, db: DBSession):
    return ApiResponse(data=notes.change_storage(db, user, note_id, payload))
