from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.user import User


def find_identity(db: Session, identity: str) -> User | None:
    normalized = identity.strip().lower()
    return db.scalar(
        select(User).where(
            or_(func.lower(User.username) == normalized, func.lower(User.email) == normalized)
        )
    )


def find_duplicate(db: Session, username: str, email: str) -> User | None:
    return db.scalar(
        select(User).where(
            or_(
                func.lower(User.username) == username.lower(),
                func.lower(User.email) == email.lower(),
            )
        )
    )


def get_user(db: Session, user_id: str) -> User | None:
    return db.get(User, user_id)


def add_user(db: Session, **values) -> User:
    user = User(**values)
    db.add(user)
    db.flush()
    return user
