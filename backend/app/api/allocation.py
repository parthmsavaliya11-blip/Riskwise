"""Allocation tracker endpoint.

Reads live/CSV holdings through the provider, the target split from the DB, and
returns the full drift / rebalance report from ``services.allocation``. This is
Module 1's core read view.
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.context import current_user_id
from ..core.config import settings
from ..core.disclaimers import with_disclaimer
from ..db import get_db
from ..holdings import load_holdings
from ..models import Bucket
from ..services.allocation import (
    BucketActual,
    BucketTarget,
    analyze_allocation,
)

router = APIRouter(prefix="/api", tags=["allocation"])


@router.get("/allocation")
def get_allocation(db: Session = Depends(get_db)) -> dict:
    holdings = load_holdings()

    # Aggregate current value + cost basis per bucket from holdings.
    value_by_bucket: dict[str, float] = defaultdict(float)
    invested_by_bucket: dict[str, float] = defaultdict(float)
    for h in holdings:
        value_by_bucket[h.bucket] += h.current_value
        invested_by_bucket[h.bucket] += h.invested

    actuals = [
        BucketActual(
            name=name,
            current_value=value_by_bucket[name],
            invested=invested_by_bucket[name],
        )
        for name in value_by_bucket
    ]

    stmt = (
        select(Bucket)
        .where(Bucket.user_id == current_user_id())
        .order_by(Bucket.target_pct.desc())
    )
    targets = [
        BucketTarget(name=b.name, target_pct=b.target_pct, tolerance_pct=b.tolerance_pct)
        for b in db.scalars(stmt)
    ]

    report = analyze_allocation(targets, actuals)
    return with_disclaimer(report)
