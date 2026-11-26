import re
from datetime import datetime, time, timedelta, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.problem import Problem
from app.models.user import User, utcnow
from app.repositories import problems as repository
from app.repositories.focus import lock_user
from app.schemas.problem import ProblemCreate, ProblemEdit, ProblemPage, ProblemRead, ProblemStatus


def context(user: User):
    zone = ZoneInfo(user.timezone)
    today = utcnow().replace(tzinfo=timezone.utc).astimezone(zone).date()
    start = datetime.combine(today, time(), zone).astimezone(timezone.utc).replace(tzinfo=None)
    end = (
        datetime.combine(today + timedelta(days=1), time(), zone)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )
    return today, start, end


def list_problems(db: Session, user: User, *, bucket, q, page, page_size):
    today, start, end = context(user)
    counts = repository.counts(db, user.id, q, start, end)
    items = db.scalars(
        repository.query(user.id, bucket, q, start, end)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return ProblemPage(
        items=[ProblemRead.model_validate(item) for item in items],
        total=counts[bucket],
        counts=counts,
        page=page,
        page_size=page_size,
        today=today,
        timezone=user.timezone,
    )


def persist(db: Session, row: Problem):
    db.flush()
    value = ProblemRead.model_validate(row)
    db.commit()
    return value


def get_problem(db: Session, user: User, problem_id: str):
    row = db.scalar(select(Problem).where(Problem.id == problem_id, Problem.user_id == user.id))
    if row is None:
        raise AppError(404, 40408, "Problem not found")
    return ProblemRead.model_validate(row)


def create(db: Session, user: User, payload: ProblemCreate):
    now = utcnow()
    row = Problem(user_id=user.id, content=payload.content, created_at=now, updated_at=now)
    db.add(row)
    return persist(db, row)


def edit(db: Session, user: User, problem_id: str, payload: ProblemEdit | ProblemStatus):
    lock_user(db, user.id)
    row = db.scalar(
        select(Problem)
        .where(Problem.id == problem_id, Problem.user_id == user.id)
        .with_for_update()
    )
    if row is None:
        raise AppError(404, 40408, "Problem not found")
    if row.revision != payload.expected_revision:
        raise AppError(409, 40912, "Problem changed; reload")
    now = utcnow()
    if isinstance(payload, ProblemStatus):
        if row.is_resolved == payload.is_resolved:
            return persist(
                db, row
            )  # Repeated same-state updates retain the original resolution time.
        row.is_resolved = payload.is_resolved
        row.resolved_at = now if payload.is_resolved else None
    else:
        row.content = payload.content
    row.updated_at = now
    row.revision = str(uuid4())
    return persist(db, row)


def export_markdown(db: Session, user: User, bucket, q):
    today, start, end = context(user)
    rows = db.scalars(repository.query(user.id, bucket, q, start, end).limit(1001)).all()
    if len(rows) > 1000:
        raise AppError(413, 41302, "Export at most 1000 problems; narrow filters")
    zone = ZoneInfo(user.timezone)

    def stamp(value):
        return value.replace(tzinfo=timezone.utc).astimezone(zone).strftime("%Y-%m-%d %H:%M:%S %z")

    names = {"today": "今日问题", "history": "历史问题", "resolved": "已解决", "all": "全部问题"}
    parts = [
        f"# FocusNest 问题备忘\n\n分类：{names[bucket]}\n\n"
        f"导出时间：{stamp(utcnow())}（{user.timezone}）\n\n共 {len(rows)} 条\n"
    ]
    size = 3 + len(parts[0].encode("utf-8"))  # Include the UTF-8 BOM.
    for index, row in enumerate(rows, 1):
        category = (
            "已解决" if row.is_resolved else "历史问题" if row.created_at < start else "今日问题"
        )
        fence = "`" * max(
            3, max((len(run) + 1 for run in re.findall(r"`+", row.content)), default=3)
        )
        part = (
            f"\n## 问题 {index}\n\n- [{'x' if row.is_resolved else ' '}] {category}\n\n"
            f"记录：{stamp(row.created_at)}\n\n更新：{stamp(row.updated_at)}\n"
        )
        if row.resolved_at:
            part += f"\n解决：{stamp(row.resolved_at)}\n"
        part += f"\n{fence}text\n{row.content}\n{fence}\n"
        size += len(part.encode("utf-8"))
        if size > 4 * 1024 * 1024:
            raise AppError(413, 41302, "Export exceeds 4 MiB; narrow filters")
        parts.append(part)
    return "".join(parts).encode("utf-8-sig"), f"FocusNest-problems-{bucket}-{today}.md"
