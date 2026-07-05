"""Password hashing (bcrypt) and signed session tokens (JWT).

Passwords are never stored or logged in plaintext — only the bcrypt hash. The token
is a JWT signed with ``settings.secret_key``; it carries only the user id + expiry.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from ..core.config import settings

_ALGO = "HS256"
# bcrypt hashes at most 72 bytes; longer inputs are truncated silently, so we cap
# explicitly to avoid surprising behaviour.
_MAX_PW_BYTES = 72


def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:_MAX_PW_BYTES]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:_MAX_PW_BYTES], password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_token(user_id: str, session_id: str) -> str:
    payload = {
        "sub": user_id,
        "sid": session_id,  # ties the token to a server-side Session row
        "exp": datetime.now(timezone.utc) + timedelta(days=settings.jwt_expire_days),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGO)


def decode_token(token: str) -> dict | None:
    """Return the decoded session-token payload ({'sub','sid',...}), or None if
    invalid/expired. Purpose tokens (verify/reset) are rejected here."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGO])
        if payload.get("purpose"):  # purpose tokens are not session tokens
            return None
        return payload
    except Exception:
        return None


def create_purpose_token(user_id: str, purpose: str, minutes: int) -> str:
    """A short-lived, single-purpose token (email verification / password reset)."""
    payload = {
        "sub": user_id,
        "purpose": purpose,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGO)


def decode_purpose_token(token: str, purpose: str) -> str | None:
    """Return the user id if the token is valid AND matches the expected purpose."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGO])
        if payload.get("purpose") != purpose:
            return None
        return payload.get("sub")
    except Exception:
        return None
