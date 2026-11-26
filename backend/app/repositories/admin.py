from datetime import datetime

from sqlalchemy import and_, case, distinct, func, or_, select, update
from sqlalchemy.orm import Session

from app.models.auth_session import AuthSession
from app.models.user import User


def online_conditions(now: datetime, cutoff: datetime):
    return (
        AuthSession.revoked_at.is_(None),
        AuthSession.expires_at > now,
        AuthSession.last_seen_at >= cutoff,
        AuthSession.last_seen_at <= now,
    )


def overview_counts(db: Session, starts: dict[str, datetime], now: datetime, cutoff: datetime):
    columns = [func.count(User.id).label("registered_total")]
    for label, start in starts.items():
        columns.append(
            func.coalesce(
                func.sum(
                    case((and_(User.created_at >= start, User.created_at <= now), 1), else_=0)
                ),
                0,
            ).label(label)
        )
    columns.append(
        func.coalesce(func.sum(case((User.role == "admin", 1), else_=0)), 0).label("administrators")
    )
    result = dict(db.execute(select(*columns).select_from(User)).mappings().one())
    result["online_users"] = db.scalar(
        select(func.count(distinct(AuthSession.user_id)))
        .join(User, User.id == AuthSession.user_id)
        .where(*online_conditions(now, cutoff))
    )
    return result


def list_users(
    db: Session,
    now: datetime,
    cutoff: datetime,
    page: int,
    page_size: int,
    search: str,
    role: str | None,
    online: bool | None,
):
    activity = (
        select(
            AuthSession.user_id,
            func.max(AuthSession.created_at).label("last_login_at"),
            func.max(
                case((AuthSession.last_seen_at <= now, AuthSession.last_seen_at), else_=None)
            ).label("last_seen_at"),
            func.max(case((and_(*online_conditions(now, cutoff)), 1), else_=0)).label("online"),
        )
        .where(AuthSession.created_at <= now)
        .group_by(AuthSession.user_id)
        .subquery()
    )
    is_online = func.coalesce(activity.c.online, 0) == 1
    conditions = []
    if search:
        conditions.append(
            or_(
                User.username.icontains(search, autoescape=True),
                User.email.icontains(search, autoescape=True),
                User.nickname.icontains(search, autoescape=True),
            )
        )
    if role is not None:
        conditions.append(User.role == role)
    if online is not None:
        conditions.append(is_online if online else ~is_online)
    base = User.__table__.outerjoin(activity, User.id == activity.c.user_id)
    total = db.scalar(select(func.count(User.id)).select_from(base).where(*conditions))
    # Select an explicit metadata allowlist: no password hashes or business content.
    rows = (
        db.execute(
            select(
                User.id,
                User.username,
                User.email,
                User.nickname,
                User.role,
                User.created_at,
                activity.c.last_login_at,
                activity.c.last_seen_at,
                is_online.label("online"),
            )
            .select_from(base)
            .where(*conditions)
            .order_by(User.created_at.desc(), User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .mappings()
        .all()
    )
    return rows, total


def touch_presence(
    db: Session, session_id: str, user_id: str, now: datetime, write_cutoff: datetime
) -> None:
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
            or_(AuthSession.last_seen_at.is_(None), AuthSession.last_seen_at < write_cutoff),
        )
        .values(last_seen_at=now)
        .execution_options(synchronize_session=False)
    )
