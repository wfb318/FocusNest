import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.core.exceptions import AppError

password_hasher = PasswordHash.recommended()


def signing_key() -> str:
    key = get_settings().jwt_secret.get_secret_value()
    if len(key) < 32:
        raise AppError(503, 50302, "Authentication signing key is not configured")
    return key


@lru_cache
def dummy_password_hash() -> str:
    return password_hasher.hash(secrets.token_urlsafe(32))


def create_access_token(user_id: str, session_id: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": user_id,
            "sid": session_id,
            "type": "access",
            "iat": now,
            "exp": now + timedelta(minutes=settings.access_token_minutes),
            "iss": "focusnest",
            "aud": "focusnest-api",
        },
        signing_key(),
        algorithm="HS256",
    )


def decode_access_token(token: str) -> dict:
    try:
        claims = jwt.decode(
            token,
            signing_key(),
            algorithms=["HS256"],
            issuer="focusnest",
            audience="focusnest-api",
            options={"require": ["exp", "iat", "sub", "sid", "type"]},
        )
        if claims["type"] != "access" or not isinstance(claims["sid"], str):
            raise jwt.InvalidTokenError()
        return claims
    except jwt.InvalidTokenError:
        raise AppError(401, 40101, "Invalid or expired authentication") from None


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
