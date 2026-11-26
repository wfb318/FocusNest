from datetime import date
from typing import Annotated

from fastapi import APIRouter, Header, Query

from app.api.deps import CurrentUser, DBSession
from app.core.exceptions import AppError
from app.schemas.common import ApiResponse
from app.schemas.journal import JournalDay, JournalMigrationCleanup, JournalPage
from app.services import journals

router = APIRouter(prefix="/journals", tags=["journals"])


def require_legacy(access: str | None) -> None:
    if access != "legacy-migration":
        raise AppError(403, 40320, "Journal is local; explicitly open legacy records")


@router.get("/today", response_model=ApiResponse[JournalDay])
def today(user: CurrentUser, db: DBSession, x_focusnest_journal_access: str | None = Header(None)):
    require_legacy(x_focusnest_journal_access)
    return ApiResponse(data=journals.get_day(db, user, journals.today(user)))


@router.get("", response_model=ApiResponse[JournalPage])
def list_entries(
    user: CurrentUser,
    db: DBSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    start_date: date | None = None,
    end_date: date | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    x_focusnest_journal_access: str | None = Header(None),
):
    require_legacy(x_focusnest_journal_access)
    return ApiResponse(
        data=journals.list_entries(
            db, user, page=page, page_size=page_size, start_date=start_date, end_date=end_date, q=q
        )
    )


@router.get("/{entry_date}", response_model=ApiResponse[JournalDay])
def get_day(
    entry_date: date,
    user: CurrentUser,
    db: DBSession,
    x_focusnest_journal_access: str | None = Header(None),
):
    require_legacy(x_focusnest_journal_access)
    return ApiResponse(data=journals.get_day(db, user, entry_date))


@router.put("/{entry_date}", response_model=ApiResponse[None])
def save(entry_date: date, user: CurrentUser):
    # No body schema: reject without validating/echoing a private draft sent by an old client.
    raise AppError(403, 40321, "Cloud journal writes are disabled; save locally")


@router.delete("/{entry_date}", response_model=ApiResponse[None])
def delete_entry(
    entry_date: date,
    user: CurrentUser,
):
    raise AppError(403, 40321, "Legacy journal deletion is disabled")


@router.post("/{entry_date}/migration-cleanup", response_model=ApiResponse[dict[str, bool]])
def cleanup_migrated_copy(
    entry_date: date,
    payload: JournalMigrationCleanup,
    user: CurrentUser,
    db: DBSession,
    x_focusnest_journal_access: str | None = Header(None),
):
    require_legacy(x_focusnest_journal_access)
    return ApiResponse(data=journals.cleanup_migrated_copy(db, user, entry_date, payload))
