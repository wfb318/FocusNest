from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Header, Query

from app.api.deps import CurrentUser, DBSession
from app.schemas.common import ApiResponse
from app.schemas.journal import JournalDay, JournalPage, JournalRead, JournalSave
from app.services import encrypted_journals
from app.services.journals import today as user_today

router = APIRouter(prefix="/journals/encrypted", tags=["encrypted journals"])
ExplicitAccess = Annotated[Literal["cloud-encrypted"], Header(alias="X-FocusNest-Journal-Access")]


@router.get("", response_model=ApiResponse[JournalPage])
def list_entries(
    user: CurrentUser,
    db: DBSession,
    access: ExplicitAccess,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    start_date: date | None = None,
    end_date: date | None = None,
):
    return ApiResponse(
        data=encrypted_journals.list_entries(db, user, page, page_size, start_date, end_date)
    )


@router.get("/today", response_model=ApiResponse[JournalDay])
def today(user: CurrentUser, db: DBSession, access: ExplicitAccess):
    return ApiResponse(data=encrypted_journals.get_day(db, user, user_today(user)))


@router.get("/{entry_date}", response_model=ApiResponse[JournalDay])
def get_day(entry_date: date, user: CurrentUser, db: DBSession, access: ExplicitAccess):
    return ApiResponse(data=encrypted_journals.get_day(db, user, entry_date))


@router.put("/{entry_date}", response_model=ApiResponse[JournalRead])
def save(
    entry_date: date, payload: JournalSave, user: CurrentUser, db: DBSession, access: ExplicitAccess
):
    return ApiResponse(data=encrypted_journals.save(db, user, entry_date, payload))


@router.delete("/{entry_date}", response_model=ApiResponse[None])
def delete(
    entry_date: date,
    user: CurrentUser,
    db: DBSession,
    access: ExplicitAccess,
    revision: Annotated[str, Query(min_length=36, max_length=36)],
):
    encrypted_journals.delete(db, user, entry_date, revision)
    return ApiResponse(message="Encrypted journal deleted")
