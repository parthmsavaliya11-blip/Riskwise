"""Bucket configuration — the investor's target capital split.

A bucket has a name, a target % of capital, and a tolerance band (e.g. F&O 20% ±5%).
The set is edited as a whole on the Allocation screen, so the write endpoint replaces
all buckets at once (simplest mental model: "this is my plan"). Defaults are seeded
on first run so the app is useful immediately.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..db import SessionLocal, get_db
from ..models import Bucket

router = APIRouter(prefix="/api/buckets", tags=["buckets"])

# The owner's starting plan; also the "reset to defaults" target.
DEFAULT_BUCKETS = [
    {"name": "F&O", "target_pct": 20.0, "tolerance_pct": 5.0},
    {"name": "Long-term", "target_pct": 30.0, "tolerance_pct": 5.0},
    {"name": "Swing", "target_pct": 50.0, "tolerance_pct": 5.0},
]


class BucketIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    target_pct: float = Field(ge=0, le=100)
    tolerance_pct: float = Field(default=5.0, ge=0, le=100)


class BucketOut(BucketIn):
    id: int


def _to_out(b: Bucket) -> dict:
    return {
        "id": b.id,
        "name": b.name,
        "target_pct": b.target_pct,
        "tolerance_pct": b.tolerance_pct,
    }


def _list(db: Session) -> list[Bucket]:
    stmt = (
        select(Bucket)
        .where(Bucket.user_id == settings.default_user_id)
        .order_by(Bucket.target_pct.desc(), Bucket.name)
    )
    return list(db.scalars(stmt))


@router.get("")
def list_buckets(db: Session = Depends(get_db)) -> dict:
    rows = [_to_out(b) for b in _list(db)]
    target_sum = round(sum(r["target_pct"] for r in rows), 2)
    return {
        "buckets": rows,
        "target_sum_pct": target_sum,
        "targets_valid": abs(target_sum - 100.0) < 0.01 if rows else False,
    }


@router.put("")
def replace_buckets(payload: list[BucketIn], db: Session = Depends(get_db)) -> dict:
    """Replace the whole bucket set for this user (the 'save my plan' action)."""
    db.query(Bucket).filter(Bucket.user_id == settings.default_user_id).delete()
    for item in payload:
        db.add(
            Bucket(
                user_id=settings.default_user_id,
                name=item.name.strip(),
                target_pct=item.target_pct,
                tolerance_pct=item.tolerance_pct,
            )
        )
    db.commit()
    return list_buckets(db)


@router.post("/reset-defaults")
def reset_defaults(db: Session = Depends(get_db)) -> dict:
    db.query(Bucket).filter(Bucket.user_id == settings.default_user_id).delete()
    for item in DEFAULT_BUCKETS:
        db.add(Bucket(user_id=settings.default_user_id, **item))
    db.commit()
    return list_buckets(db)


def seed_default_buckets() -> None:
    """Seed the default split on first run if the user has no buckets yet.

    Called from the app lifespan so a fresh install lands on a sensible plan
    instead of an empty allocation screen.
    """
    db = SessionLocal()
    try:
        existing = db.scalar(
            select(Bucket).where(Bucket.user_id == settings.default_user_id).limit(1)
        )
        if existing is None:
            for item in DEFAULT_BUCKETS:
                db.add(Bucket(user_id=settings.default_user_id, **item))
            db.commit()
    finally:
        db.close()
