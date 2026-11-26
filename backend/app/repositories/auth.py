from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.auth_session import AuthSession
from app.models.user import utcnow


def add_session(db: Session, **values) -> AuthSession:
    session = AuthSession(**values)
    db.add(session)
    db.flush()
    return session


def get_session(db: Session, session_id: str) -> AuthSession | None:
    return db.get(AuthSession, session_id)


def rotate_session(db: Session, old_hash: str, new_hash: str) -> AuthSession | None:
    # Conditional UPDATE makes rotation single-use even for concurrent requests.
    statement = (
        update(AuthSession)
        .where(
            AuthSession.refresh_token_hash == old_hash,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > utcnow(),
        )
        .values(refresh_token_hash=new_hash)
    )
    if db.execute(statement).rowcount != 1:
        return None
    return db.scalar(select(AuthSession).where(AuthSession.refresh_token_hash == new_hash))


def revoke_session(db: Session, token_hash: str) -> None:
    db.execute(
        update(AuthSession)
        .where(
            AuthSession.refresh_token_hash == token_hash,
            AuthSession.revoked_at.is_(None),
        )
        .values(revoked_at=utcnow())
    )
