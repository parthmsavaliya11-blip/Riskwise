"""Authentication: signup, login, logout, and 'who am I'.

Sessions are a signed JWT in an httpOnly cookie, so a login persists per browser
until logout (and can't be read by page scripts). The very first account to sign up
becomes the owner/admin and inherits any pre-existing single-user data, so the
existing portfolio moves onto the owner's account rather than a stranger's.
"""

from __future__ import annotations

import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..auth.deps import SESSION_COOKIE, require_user
from ..auth.email import send_password_reset, send_verification
from ..auth.ratelimit import rate_limit
from ..auth.security import (
    create_token,
    decode_purpose_token,
    hash_password,
    verify_password,
)
from ..core.config import settings
from ..db import get_db
from ..models import Bucket, CashFlow, Position, Trade, User

router = APIRouter(prefix="/api/auth", tags=["auth"])

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,20}$")


class SignupIn(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


def _user_out(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "username": u.username,
        "email_verified": u.email_verified,
        "is_admin": u.is_admin,
        "username_changes": u.username_changes,
        "username_changes_left": max(0, 3 - u.username_changes),
    }


def _set_session(response: Response, user_id: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=create_token(user_id),
        max_age=settings.jwt_expire_days * 86400,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.post("/signup", dependencies=[Depends(rate_limit(5, 3600))])
def signup(payload: SignupIn, response: Response, db: Session = Depends(get_db)) -> dict:
    email = payload.email.strip().lower()
    username = payload.username.strip()
    if not _USERNAME_RE.match(username):
        raise HTTPException(400, "Username must be 3–20 letters, numbers or underscores.")
    if db.scalar(select(User).where(func.lower(User.email) == email)):
        raise HTTPException(409, "An account with this email already exists.")
    if db.scalar(select(User).where(func.lower(User.username) == username.lower())):
        raise HTTPException(409, "That username is taken.")

    is_first = db.scalar(select(func.count()).select_from(User)) == 0
    user = User(
        id=str(uuid.uuid4()),
        email=email,
        username=username,
        password_hash=hash_password(payload.password),
        email_verified=False,
        is_admin=is_first,  # first account is the owner/admin
    )
    db.add(user)

    if is_first:
        # Adopt any pre-existing single-user data onto the owner's account.
        for model in (Position, Bucket, Trade, CashFlow):
            db.execute(
                update(model)
                .where(model.user_id == settings.default_user_id)
                .values(user_id=user.id)
            )
    db.commit()

    _set_session(response, user.id)
    dev_link = send_verification(user)
    out = {"user": _user_out(user)}
    # In dev without Resend configured, hand back the link so the flow is testable.
    if not settings.email_enabled and settings.environment == "development":
        out["dev_verify_link"] = dev_link
    return out


@router.post("/login", dependencies=[Depends(rate_limit(10, 900))])
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)) -> dict:
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Wrong email or password.")
    _set_session(response, user.id)
    return {"user": _user_out(user)}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(require_user)) -> dict:
    return {"user": _user_out(user)}


# --- Profile -------------------------------------------------------------
class UsernameIn(BaseModel):
    username: str = Field(min_length=3, max_length=20)


class PasswordChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


@router.put("/username")
def change_username(
    payload: UsernameIn, user: User = Depends(require_user), db: Session = Depends(get_db)
) -> dict:
    new = payload.username.strip()
    if not _USERNAME_RE.match(new):
        raise HTTPException(400, "Username must be 3–20 letters, numbers or underscores.")
    if new.lower() == user.username.lower():
        raise HTTPException(400, "That's already your username.")
    if user.username_changes >= 3:
        raise HTTPException(403, "You've used all 3 username changes.")
    if db.scalar(
        select(User).where(func.lower(User.username) == new.lower(), User.id != user.id)
    ):
        raise HTTPException(409, "That username is taken.")
    user.username = new
    user.username_changes += 1
    db.commit()
    return {"user": _user_out(user)}


@router.put("/password")
def change_password(
    payload: PasswordChangeIn, user: User = Depends(require_user), db: Session = Depends(get_db)
) -> dict:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(401, "Your current password is incorrect.")
    if payload.new_password == payload.current_password:
        raise HTTPException(400, "The new password must be different.")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"ok": True}


# --- Email verification & password reset ---------------------------------
class TokenIn(BaseModel):
    token: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


@router.post("/verify")
def verify_email(payload: TokenIn, db: Session = Depends(get_db)) -> dict:
    """Confirm an email from the link (public — the token is the proof)."""
    uid = decode_purpose_token(payload.token, "verify")
    user = db.get(User, uid) if uid else None
    if user is None:
        raise HTTPException(400, "This verification link is invalid or has expired.")
    if not user.email_verified:
        user.email_verified = True
        db.commit()
    return {"ok": True, "user": _user_out(user)}


@router.post("/verify/resend", dependencies=[Depends(rate_limit(5, 3600))])
def resend_verification(user: User = Depends(require_user)) -> dict:
    if user.email_verified:
        return {"ok": True, "already_verified": True}
    dev_link = send_verification(user)
    out = {"ok": True}
    if not settings.email_enabled and settings.environment == "development":
        out["dev_verify_link"] = dev_link
    return out


@router.post("/forgot-password", dependencies=[Depends(rate_limit(5, 3600))])
def forgot_password(payload: ForgotIn, db: Session = Depends(get_db)) -> dict:
    """Always returns ok — never reveal whether an email is registered."""
    email = payload.email.strip().lower()
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    out = {"ok": True}
    if user is not None:
        dev_link = send_password_reset(user)
        if not settings.email_enabled and settings.environment == "development":
            out["dev_reset_link"] = dev_link
    return out


@router.post("/reset-password", dependencies=[Depends(rate_limit(10, 3600))])
def reset_password(payload: ResetIn, db: Session = Depends(get_db)) -> dict:
    uid = decode_purpose_token(payload.token, "reset")
    user = db.get(User, uid) if uid else None
    if user is None:
        raise HTTPException(400, "This reset link is invalid or has expired. Request a new one.")
    user.password_hash = hash_password(payload.password)
    db.commit()
    return {"ok": True}
