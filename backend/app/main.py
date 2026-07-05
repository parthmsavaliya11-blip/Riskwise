"""FastAPI application entry point.

Run from the backend/ folder with:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import (
    ai,
    allocation,
    auth,
    basket,
    buckets,
    fno,
    hedge,
    instruments,
    journal,
    options,
    portfolio,
    positions,
    risk,
    sizing,
    status,
    symbols,
)
from pathlib import Path

from fastapi.staticfiles import StaticFiles

from .api.buckets import seed_default_buckets
from .auth.deps import require_user
from .core.config import PROJECT_ROOT, settings
from .db import init_db


def _warm_market() -> None:
    """Parse the instrument master, open the Angel session, and pre-fetch every
    holding's live price ahead of the first request — so the portfolio loads warm
    and live-correct instead of cold (slow, and prone to falling back to cost
    prices before the feed is ready). Best-effort, off the hot path."""
    try:
        from .market import get_market

        mkt = get_market()
        if mkt is None:
            return
        mkt._build()
        from .holdings import load_holdings

        load_holdings()  # logs in + batch-prefetches each holding's LTP into the cache
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables on startup (safe to run every time), then seed the
    # default allocation plan so a fresh install isn't an empty screen.
    init_db()
    seed_default_buckets()
    # Warm the live market feed in the background (never blocks startup).
    import threading

    threading.Thread(target=_warm_market, daemon=True).start()
    yield


_IS_PROD = settings.environment == "production"

# In production the interactive API docs are turned off (they'd expose the whole API
# surface publicly); they stay on in development at /docs.
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if _IS_PROD else "/docs",
    redoc_url=None if _IS_PROD else "/redoc",
    openapi_url=None if _IS_PROD else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request, call_next):
    """Baseline hardening headers (finance app served over HTTPS)."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"  # no clickjacking / embedding
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if _IS_PROD:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response

# Public routes — no login required.
app.include_router(status.router)
app.include_router(auth.router)

# Everything below requires a signed-in user and is automatically scoped to them
# (require_user resolves the session cookie and pins the request to that user).
_auth = [Depends(require_user)]
app.include_router(portfolio.router, dependencies=_auth)
app.include_router(buckets.router, dependencies=_auth)
app.include_router(allocation.router, dependencies=_auth)
app.include_router(sizing.router, dependencies=_auth)
app.include_router(hedge.router, dependencies=_auth)
app.include_router(options.router, dependencies=_auth)
app.include_router(risk.router, dependencies=_auth)
app.include_router(journal.router, dependencies=_auth)
app.include_router(ai.router, dependencies=_auth)
app.include_router(positions.router, dependencies=_auth)
app.include_router(symbols.router, dependencies=_auth)
app.include_router(instruments.router, dependencies=_auth)
app.include_router(fno.router, dependencies=_auth)
app.include_router(basket.router, dependencies=_auth)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "app": settings.app_name}


# --- Serve the built frontend (production single-service deploy) ------------
# In production we build the React app to frontend/dist and serve it from here, so
# the API and the site share one origin (clean, secure httpOnly cookies — no CORS).
# Mounted LAST, so /api/*, /health and /docs still win; everything else is the SPA.
# In dev this folder doesn't exist, so nothing is mounted (Vite serves the frontend).
_DIST = PROJECT_ROOT / "frontend" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_DIST), html=True), name="frontend")
