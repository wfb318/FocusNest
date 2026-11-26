from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.problem import Problem


def filters(user_id: str, q: str | None):
    result = [Problem.user_id == user_id]
    if q:
        # Treat %, _ and the escape character as text, not search wildcards.
        value = q.replace("!", "!!").replace("%", "!%").replace("_", "!_")
        result.append(Problem.content.like(f"%{value}%", escape="!"))
    return result


def buckets(start: datetime, end: datetime):
    return {
        "today": (
            Problem.is_resolved.is_(False)
            & (Problem.created_at >= start)
            & (Problem.created_at < end)
        ),
        "history": (Problem.is_resolved.is_(False) & (Problem.created_at < start)),
        "resolved": Problem.is_resolved.is_(True),
    }


def query(user_id, bucket, q, start, end):
    statement = select(Problem).where(*filters(user_id, q))
    if bucket != "all":
        statement = statement.where(buckets(start, end)[bucket])
    if bucket == "resolved":
        return statement.order_by(Problem.resolved_at.desc(), Problem.id.desc())
    return statement.order_by(Problem.created_at.desc(), Problem.id.desc())


def counts(db: Session, user_id: str, q: str | None, start: datetime, end: datetime):
    conditions = buckets(start, end)
    row = (
        db.execute(
            select(
                *[
                    func.coalesce(func.sum(case((condition, 1), else_=0)), 0).label(name)
                    for name, condition in conditions.items()
                ],
                func.count().label("all"),
            ).where(*filters(user_id, q))
        )
        .mappings()
        .one()
    )
    return {name: int(value) for name, value in row.items()}
