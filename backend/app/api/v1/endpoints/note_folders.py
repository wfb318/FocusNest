from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DBSession
from app.schemas.common import ApiResponse
from app.schemas.note_folder import FolderCreate, FolderRead, FolderRename
from app.services import note_folders

router = APIRouter(prefix="/note-folders", tags=["note-folders"])


@router.get("", response_model=ApiResponse[list[FolderRead]])
def list_folders(user: CurrentUser, db: DBSession):
    return ApiResponse(data=note_folders.list_folders(db, user))


@router.post("", status_code=201, response_model=ApiResponse[FolderRead])
def create(payload: FolderCreate, user: CurrentUser, db: DBSession):
    return ApiResponse(data=note_folders.create(db, user, payload))


@router.patch("/{folder_id}", response_model=ApiResponse[FolderRead])
def rename(folder_id: str, payload: FolderRename, user: CurrentUser, db: DBSession):
    return ApiResponse(data=note_folders.rename(db, user, folder_id, payload))


@router.delete("/{folder_id}", response_model=ApiResponse[None])
def delete_folder(
    folder_id: str,
    revision: Annotated[str, Query(min_length=36, max_length=36)],
    user: CurrentUser,
    db: DBSession,
):
    note_folders.delete_folder(db, user, folder_id, revision)
    return ApiResponse(message="Folder deleted; notes preserved")
