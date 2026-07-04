"""Position-sizing endpoint.

Stateless: takes the trade parameters, returns max quantity/lots and the rupee
risk from ``services.sizing``. No holdings or DB needed.
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..core.disclaimers import with_disclaimer
from ..services.sizing import SizingInput, size_position

router = APIRouter(prefix="/api", tags=["sizing"])


class SizingRequest(BaseModel):
    account_size: float = Field(gt=0)
    risk_per_trade_pct: float = Field(gt=0, le=100)
    entry_price: float = Field(gt=0)
    stop_price: float = Field(gt=0)
    side: str = "long"
    lot_size: int = Field(default=1, ge=1)
    bucket_room: float | None = None


@router.post("/sizing")
def calculate_sizing(req: SizingRequest) -> dict:
    result = size_position(
        SizingInput(
            account_size=req.account_size,
            risk_per_trade_pct=req.risk_per_trade_pct,
            entry_price=req.entry_price,
            stop_price=req.stop_price,
            side=req.side,
            lot_size=req.lot_size,
            bucket_room=req.bucket_room,
        )
    )
    return with_disclaimer(result)
