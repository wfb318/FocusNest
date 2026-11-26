from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import CurrentUser, DBSession
from app.schemas.common import ApiResponse
from app.schemas.problem import (
    ProblemBucket,
    ProblemCreate,
    ProblemEdit,
    ProblemPage,
    ProblemRead,
    ProblemStatus,
)
from app.services import problems

router = APIRouter(prefix="/problems", tags=["problems"])


@router.get("", response_model=ApiResponse[ProblemPage])
def list_problems(
    user: CurrentUser,
    db: DBSession,
    bucket: ProblemBucket = "today",
    q: Annotated[str | None, Query(max_length=100)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return ApiResponse(
        data=problems.list_problems(db, user, bucket=bucket, q=q, page=page, page_size=page_size)
    )


@router.get("/export")
def export(
    user: CurrentUser,
    db: DBSession,
    bucket: ProblemBucket = "all",
    q: Annotated[str | None, Query(max_length=100)] = None,
):
    content, filename = problems.export_markdown(db, user, bucket, q)
    return Response(
        content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("", status_code=201, response_model=ApiResponse[ProblemRead])
def create(payload: ProblemCreate, user: CurrentUser, db: DBSession):
    return ApiResponse(data=problems.create(db, user, payload))


@router.put("/{problem_id}", response_model=ApiResponse[ProblemRead])
def edit(problem_id: str, payload: ProblemEdit, user: CurrentUser, db: DBSession):
    return ApiResponse(data=problems.edit(db, user, problem_id, payload))


@router.get("/{problem_id}", response_model=ApiResponse[ProblemRead])
def detail(problem_id: str, user: CurrentUser, db: DBSession):
    return ApiResponse(data=problems.get_problem(db, user, problem_id))


@router.patch("/{problem_id}/status", response_model=ApiResponse[ProblemRead])
def status(problem_id: str, payload: ProblemStatus, user: CurrentUser, db: DBSession):
    return ApiResponse(data=problems.edit(db, user, problem_id, payload))
