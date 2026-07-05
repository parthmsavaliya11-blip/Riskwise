"""One-time migration: copy this machine's local SQLite data into a Postgres DB
(Neon) for the production deploy, so your portfolio comes with you.

Run once, BEFORE going live (it wipes the target tables, so don't run it after real
users have added data on the live site).

Usage (from backend/, with the venv active):
    # PowerShell:
    $env:TARGET_DATABASE_URL = "postgresql://USER:PASSWORD@HOST/neondb?sslmode=require"
    python migrate_to_postgres.py

Copies: users, buckets, positions, trades, cash flows. User ids (uuids) are preserved
so each user's data stays linked; the integer ids of the other tables are reassigned
by Postgres (nothing references them).
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.core.config import DATA_DIR
from app.db import _normalize_url
from app.models import Base, Bucket, CashFlow, Position, Trade, User

SOURCE = os.environ.get("SOURCE_DATABASE_URL", f"sqlite:///{(DATA_DIR / 'risk.db').as_posix()}")
TARGET = os.environ.get("TARGET_DATABASE_URL")

# users first (others carry user_id referencing it); ids of non-user tables are dropped.
MODELS = [User, Bucket, Position, Trade, CashFlow]


def main() -> None:
    if not TARGET:
        print("ERROR: set TARGET_DATABASE_URL to your Neon connection string.")
        sys.exit(1)

    src = create_engine(_normalize_url(SOURCE), future=True)
    tgt = create_engine(_normalize_url(TARGET), pool_pre_ping=True, future=True)

    print(f"Source: {SOURCE.split('@')[-1]}")
    print(f"Target: {TARGET.split('@')[-1]}")
    Base.metadata.create_all(bind=tgt)

    total = 0
    with Session(src) as s, Session(tgt) as t:
        for model in reversed(MODELS):  # clear target for a clean first copy
            t.execute(delete(model))
        t.commit()

        for model in MODELS:
            rows = list(s.scalars(select(model)))
            for r in rows:
                data = {c.name: getattr(r, c.name) for c in model.__table__.columns}
                if model is not User:
                    data.pop("id", None)  # let Postgres assign fresh integer ids
                t.execute(model.__table__.insert().values(**data))
            t.commit()
            print(f"  {model.__tablename__:12} {len(rows):>4} rows")
            total += len(rows)

    print(f"Done — {total} rows migrated to Postgres.")


if __name__ == "__main__":
    main()
