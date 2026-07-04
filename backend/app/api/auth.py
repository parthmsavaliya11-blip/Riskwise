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
from ..auth.security import create_token, hash_password, verify_password
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


@router.post("/signup")
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
    return {"user": _user_out(user)}


@router.post("/login")
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
