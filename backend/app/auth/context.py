"""Request-scoped current user.

The whole app was written single-user (every row filtered by ``user_id``). To go
multi-user with minimal, auditable change, the authenticated user's id is stashed
in a ContextVar per request by the ``require_user`` dependency, and every data-access
path reads it via ``current_user_id()`` instead of the old fixed default.

Safety: ``require_user`` is an **async** dependency, so it sets the var in the
request's own context; Starlette copies that context into the threadpool when it runs
the sync endpoint, so the value is visible to the endpoint and everything it calls —
and never leaks across requests (each request has its own context). Outside a request
(startup warm-up, scripts) the var is unset and we fall back to the legacy default id.
"""

from __future__ import annotations

from contextvars import ContextVar

from ..core.config import settings

_uid: ContextVar[str | None] = ContextVar("rw_current_user", default=None)


def set_current_user(user_id: str | None) -> None:
    _uid.set(user_id)


def current_user_id() -> str:
    """The logged-in user's id for this request, or the legacy default outside one."""
    return _uid.get() or settings.default_user_id
