from datetime import date

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession
from app.schemas.common import ApiResponse
from app.schemas.focus import FocusRead
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleEdit,
    ScheduleRemove,
    ScheduleTemplateApply,
    ScheduleTemplateRead,
    ScheduleTemplateReview,
    ScheduleTemplateSave,
    ScheduleWeek,
)
from app.services import schedule_templates, schedules

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("", response_model=ApiResponse[ScheduleWeek])
def week(start_date: date, end_date: date, user: CurrentUser, db: DBSession):
    return ApiResponse(data=schedules.list_week(db, user, start_date, end_date))


@router.post("", status_code=201)
def create(payload: ScheduleCreate, user: CurrentUser, db: DBSession):
    return ApiResponse(data=schedules.create(db, user, payload))


@router.get("/templates", response_model=ApiResponse[list[ScheduleTemplateRead]])
def templates(user: CurrentUser, db: DBSession):
    return ApiResponse(data=schedule_templates.summaries(db, user))


@router.post("/templates", status_code=201, response_model=ApiResponse[ScheduleTemplateRead])
def save_template(payload: ScheduleTemplateSave, user: CurrentUser, db: DBSession):
    return ApiResponse(data=schedule_templates.save(db, user, payload))


@router.post("/templates/{template_id}/apply", response_model=ApiResponse[None])
def apply_template(
    template_id: str, payload: ScheduleTemplateApply, user: CurrentUser, db: DBSession
):
    schedule_templates.apply(db, user, template_id, payload)
    return ApiResponse(message="Template applied")


@router.get("/template-review", response_model=ApiResponse[ScheduleTemplateReview])
def template_review(user: CurrentUser, db: DBSession):
    return ApiResponse(data=schedule_templates.review_due(db, user))


@router.post("/template-review/{week_start}/keep", response_model=ApiResponse[None])
def keep_template_week(week_start: date, user: CurrentUser, db: DBSession):
    schedule_templates.keep_week(db, user, week_start)
    return ApiResponse(message="Week kept")


@router.post("/templates/carry")
def carry_template(user: CurrentUser, db: DBSession):
    return ApiResponse(data={"applied": schedule_templates.ensure_current_week(db, user)})


@router.put("/{schedule_id}")
def edit(schedule_id: str, payload: ScheduleEdit, user: CurrentUser, db: DBSession):
    return ApiResponse(data=schedules.edit(db, user, schedule_id, payload))


@router.post("/{schedule_id}/remove")
def remove(schedule_id: str, payload: ScheduleRemove, user: CurrentUser, db: DBSession):
    return ApiResponse(data=schedules.edit(db, user, schedule_id, payload, remove=True))


@router.post("/{schedule_id}/start", response_model=ApiResponse[FocusRead])
def start(schedule_id: str, occurrence_date: date, user: CurrentUser, db: DBSession):
    return ApiResponse(data=schedules.start_occurrence(db, user, schedule_id, occurrence_date))
