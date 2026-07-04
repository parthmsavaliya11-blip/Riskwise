"""Auth dependencies. ``require_user`` guards every data route and pins the request
to the logged-in user (see ``context.py`` for why it's async)."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from .context import set_current_user
from .security import decode_token

# httpOnly session cookie name.
SESSION_COOKIE = "rw_session"


async def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve the logged-in user from the session cookie, or 401. Also sets the
    request-scoped current-user so downstream data access is automatically scoped."""
    token = request.cookies.get(SESSION_COOKIE)
    user_id = decode_token(token) if token else None
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    set_current_user(user.id)
    return user


async def require_admin(user: User = Depends(require_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin only")
    return user
