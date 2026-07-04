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

# check_same_thread is a SQLite-only flag; harmless to pass conditionally.
_connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(settings.database_url, connect_args=_connect_args, future=True)
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
    _migrate_positions()


def _migrate_positions() -> None:
    """Add new ``positions`` columns to an existing SQLite db (create_all won't alter).

    Lightweight, idempotent: only adds columns that are missing, so existing rows
    (the user's holdings) are preserved.
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
