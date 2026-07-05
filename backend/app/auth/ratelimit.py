"""Lightweight in-memory rate limiting for the auth endpoints (brute-force / spam
protection). Keyed by client IP + route, fixed window.

In-memory is fine for the single Render instance we run on; if this ever scales to
multiple instances, move the counters to Redis. It fails open (never blocks a normal
user) and only trips on clearly abusive volumes.
"""

from __future__ import annotations

import time
from collections import defaultdict

from fastapi import HTTPException, Request

_hits: dict[str, list[float]] = defaultdict(list)
_last_prune = 0.0


def _client_ip(request: Request) -> str:
    # Behind Render/Cloudflare the real client is in X-Forwarded-For (first hop).
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _prune(now: float) -> None:
    # Occasionally drop empty buckets so the dict can't grow forever.
    global _last_prune
    if now - _last_prune < 300:
        return
    _last_prune = now
    for k in [k for k, v in _hits.items() if not v]:
        _hits.pop(k, None)


def rate_limit(limit: int, window_seconds: int):
    """Dependency factory: allow at most `limit` requests per `window_seconds` per IP+route."""

    def dep(request: Request) -> None:
        now = time.time()
        cutoff = now - window_seconds
        key = f"{request.url.path}:{_client_ip(request)}"
        hits = _hits[key]
        hits[:] = [t for t in hits if t > cutoff]
        if len(hits) >= limit:
            raise HTTPException(
                status_code=429,
                detail="Too many attempts. Please wait a few minutes and try again.",
            )
        hits.append(now)
        _prune(now)

    return dep
