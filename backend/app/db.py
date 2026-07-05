"""Database engine, session and init.

SQLite file by default (zero setup). Because every model carries ``user_id`` and
we go through this single module, switching to Postgres for multi-user later is a
``DATABASE_URL`` change, not a rewrite.
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .core.config import settings


def _normalize_url(url: str) -> str:
    """Make a raw DATABASE_URL SQLAlchemy-ready.

    Managed Postgres (Neon/Render) hands out ``postgres://`` or ``postgresql://``;
    point both at psycopg v3 so no separate driver guessing is needed. SQLite URLs
    pass through unchanged.
    """
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


DATABASE_URL = _normalize_url(settings.database_url)
_is_sqlite = DATABASE_URL.startswith("sqlite")

# check_same_thread is SQLite-only; Postgres gets a small pooled + pre-ping engine
# (Neon closes idle connections, so pre-ping avoids stale-connection errors).
if _is_sqlite:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False}, future=True)
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300, future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Safe to call on every startup."""
    # Import models so they register on the metadata before create_all.
    from . import models  # noqa: F401

    models.Base.metadata.create_all(bind=engine)
    if _is_sqlite:
        _migrate_positions()  # Postgres tables are created complete; only SQLite needs ALTERs


def _migrate_positions() -> None:
    """Add new ``positions`` columns to an existing SQLite db (create_all won't alter).

    Lightweight, idempotent: only adds columns that are missing, so existing rows
    (the user's holdings) are preserved. SQLite-only (uses PRAGMA).
    """
    from sqlalchemy import text

    added = {
        "tradingsymbol": "VARCHAR(64)",
        "exchange": "VARCHAR(8)",
        "token": "VARCHAR(24)",
        "lot_size": "INTEGER DEFAULT 1",
        "kind": "VARCHAR(8) DEFAULT 'EQ'",
        "side": "VARCHAR(8) DEFAULT 'buy'",
        "basket_id": "VARCHAR(36)",
        "basket_label": "VARCHAR(64)",
    }
    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text("PRAGMA table_info(positions)"))}
        for name, ddl in added.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE positions ADD COLUMN {name} {ddl}"))
