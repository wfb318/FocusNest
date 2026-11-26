from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.security import password_hasher
from app.models.user import User, utcnow
from app.repositories import admin as repository
from app.repositories import users
from app.schemas.admin import AdminOverview, AdminUserPage, AdminUserRead, PresenceRead
from app.schemas.user import Registration
from app.services.auth import AuthIdentity

ONLINE_WINDOW_SECONDS = 300
PRESENCE_WRITE_SECONDS = 30


def overview(db: Session, admin: User) -> AdminOverview:
    now = utcnow()
    zone = ZoneInfo(admin.timezone)
    today = now.replace(tzinfo=timezone.utc).astimezone(zone).date()
    local_starts = {
        "registered_today": today,
        "registered_week": today - timedelta(days=today.weekday()),
        "registered_month": today.replace(day=1),
    }
    starts = {
        label: datetime.combine(day, time(), zone).astimezone(timezone.utc).replace(tzinfo=None)
        for label, day in local_starts.items()
    }
    counts = repository.overview_counts(
        db, starts, now, now - timedelta(seconds=ONLINE_WINDOW_SECONDS)
    )
    return AdminOverview(
        **counts,
        timezone=admin.timezone,
        today=today,
        server_now=now,
        online_window_seconds=ONLINE_WINDOW_SECONDS,
    )


def list_users(
    db: Session,
    page: int,
    page_size: int,
    search: str,
    role: str | None,
    online: bool | None,
) -> AdminUserPage:
    now = utcnow()
    rows, total = repository.list_users(
        db,
        now,
        now - timedelta(seconds=ONLINE_WINDOW_SECONDS),
        page,
        page_size,
        search.strip(),
        role,
        online,
    )
    return AdminUserPage(
        items=[AdminUserRead.model_validate(dict(row)) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
        server_now=now,
        online_window_seconds=ONLINE_WINDOW_SECONDS,
    )


def heartbeat(db: Session, identity: AuthIdentity) -> PresenceRead:
    now = utcnow()
    repository.touch_presence(
        db,
        identity.session.id,
        identity.user.id,
        now,
        now - timedelta(seconds=PRESENCE_WRITE_SECONDS),
    )
    db.commit()
    return PresenceRead(server_now=now, online_window_seconds=ONLINE_WINDOW_SECONDS)


def create_administrator(db: Session, payload: Registration) -> User:
    """Server CLI only. Public registration always creates a regular user."""
    if users.find_duplicate(db, payload.username, str(payload.email)):
        raise AppError(409, 40901, "Username or email already registered")
    try:
        user = users.add_user(
            db,
            username=payload.username,
            email=str(payload.email),
            password_hash=password_hasher.hash(payload.password),
            role="admin",
        )
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        raise AppError(409, 40901, "Username or email already registered") from None


def change_role(db: Session, identity: str, role: str) -> User:
    if role not in ("user", "admin"):
        raise AppError(422, 42240, "Invalid application role")
    user = users.find_identity(db, identity.strip().lower())
    if user is None:
        raise AppError(404, 40440, "Account not found")
    user.role = role
    db.commit()
    db.refresh(user)
    return user
