from sqlalchemy.orm import Session

from app.models.user import User, utcnow
from app.schemas.user import UserUpdate


def update_profile(db: Session, user: User, payload: UserUpdate) -> User:
    for name, value in payload.model_dump(exclude_unset=True, mode="json").items():
        setattr(user, name, value)
    user.updated_at = utcnow()
    db.commit()
    db.refresh(user)
    return user
