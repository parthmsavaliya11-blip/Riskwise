"""Trade journal endpoints (Module 5).

CRUD over the ``Trade`` table plus computed performance: per-trade R-multiple and
P&L, and aggregate win rate / expectancy / profit factor from ``services.journal``.
Realised closed trades are the cash-flow source that Module 1's per-bucket XIRR will
consume later.
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth.context import current_user_id
from ..core.config import settings
from ..core.disclaimers import with_disclaimer
from ..data import get_provider
from ..db import get_db
from ..holdings import _resolve_ltp
from ..models import Position, Trade
from ..services.journal import r_multiple, review_financial_years, summarize, trade_pnl

router = APIRouter(prefix="/api/journal", tags=["journal"])


class TradeIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    bucket: str = "unassigned"
    side: str = Field(default="long", pattern="^(long|short)$")
    entry_price: float = Field(gt=0)
    stop_price: float = Field(ge=0)
    target_price: float = 0.0
    exit_price: float = 0.0          # > 0 marks the trade closed
    quantity: float = Field(gt=0)
    fees: float = 0.0
    notes: str = ""
    entry_date: str = Field(min_length=8)      # mandatory, ISO "YYYY-MM-DD" (date the trade was taken)
    exit_date: str | None = None               # required only when an exit price is supplied


class CloseIn(BaseModel):
    exit_price: float = Field(gt=0)
    exit_date: str = Field(min_length=8)        # mandatory, ISO "YYYY-MM-DD" (date the trade was closed)
    fees: float | None = None


def _parse_date(s: str | None) -> datetime | None:
    """Parse an ISO 'YYYY-MM-DD' (midnight). 400 on a bad value so dates stay trustworthy."""
    if not s:
        return None
    try:
        return datetime.fromisoformat(s[:10])
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date: {s!r} (use YYYY-MM-DD)")


def _row(t: Trade) -> dict:
    closed = t.status == "closed"
    r = pnl = None
    if closed:
        r = r_multiple(t.entry_price, t.stop_price, t.exit_price, t.side)
        pnl = trade_pnl(t.entry_price, t.exit_price, t.quantity, t.side, t.fees)
    return {
        "id": t.id,
        "symbol": t.symbol,
        "bucket": t.bucket,
        "side": t.side,
        "entry_price": t.entry_price,
        "stop_price": t.stop_price,
        "target_price": t.target_price,
        "exit_price": t.exit_price,
        "quantity": t.quantity,
        "fees": t.fees,
        "status": t.status,
        "notes": t.notes,
        "opened_at": t.opened_at.isoformat() if t.opened_at else None,
        "closed_at": t.closed_at.isoformat() if t.closed_at else None,
        # User-supplied trade dates (entry mandatory; exit set on close) — the keys the UI shows.
        "entry_date": t.opened_at.date().isoformat() if t.opened_at else None,
        "exit_date": t.closed_at.date().isoformat() if t.closed_at else None,
        "r_multiple": r,
        "pnl": pnl,
    }


def _list(db: Session) -> list[Trade]:
    stmt = (
        select(Trade)
        .where(Trade.user_id == current_user_id())
        .order_by(Trade.opened_at.desc(), Trade.id.desc())
    )
    return list(db.scalars(stmt))


@router.get("")
def list_trades(db: Session = Depends(get_db)) -> dict:
    trades = [_row(t) for t in _list(db)]
    closed = [
        {"entry": r["entry_price"], "stop": r["stop_price"], "exit": r["exit_price"],
         "quantity": r["quantity"], "side": r["side"], "fees": r["fees"]}
        for r in trades if r["status"] == "closed"
    ]
    return with_disclaimer({"trades": trades, "stats": summarize(closed)})


@router.get("/review")
def financial_year_review(db: Session = Depends(get_db)) -> dict:
    """Per-financial-year performance by segment, with cross-FY comparison.

    Indian FY (1 Apr -> 31 Mar). Trades are grouped by their EXIT date; only completed
    financial years carry allocation guidance (the current FY is flagged in-progress).
    Every figure is from ``services.journal`` — the AI explainer only narrates them.
    """
    rows = [_row(t) for t in _list(db)]
    closed = [
        {"entry": r["entry_price"], "stop": r["stop_price"], "exit": r["exit_price"],
         "quantity": r["quantity"], "side": r["side"], "fees": r["fees"],
         "bucket": r["bucket"], "exit_date": r["exit_date"]}
        for r in rows if r["status"] == "closed" and r["exit_date"]
    ]
    return with_disclaimer(review_financial_years(closed, _open_holdings(db)))


def _open_holdings(db: Session) -> list[dict]:
    """Still-open positions from My Holdings, as held-capital inputs for the FY review.

    These are NOT journal trades — a long-term position bought once and held for years
    feeds the year-end analysis by its buy date, without ever appearing in the journal.
    """
    provider = get_provider()
    positions = list(db.scalars(
        select(Position).where(Position.user_id == current_user_id())
    ))
    from ..market import get_market
    mkt = get_market()
    if mkt is not None:
        mkt.warm_positions(positions)  # one batched live-price call

    out = []
    for p in positions:
        ltp, _ = _resolve_ltp(provider, p)
        invested = p.quantity * p.avg_price
        value = p.quantity * ltp
        raw = value - invested
        side = getattr(p, "side", None) or "buy"
        out.append({
            "bucket": p.bucket,
            "invested": round(invested, 2),
            "unrealized_pnl": round(raw if side != "sell" else -raw, 2),
            "buy_date": p.buy_date.date().isoformat() if p.buy_date else None,
        })
    return out


@router.post("")
def create_trade(payload: TradeIn, db: Session = Depends(get_db)) -> dict:
    is_closed = payload.exit_price and payload.exit_price > 0
    opened_at = _parse_date(payload.entry_date)
    if opened_at is None:
        raise HTTPException(status_code=400, detail="Entry date is required.")
    closed_at = None
    if is_closed:
        closed_at = _parse_date(payload.exit_date)
        if closed_at is None:
            raise HTTPException(status_code=400, detail="Exit date is required to log a closed trade.")
        if closed_at < opened_at:
            raise HTTPException(status_code=400, detail="Exit date can't be before the entry date.")
    t = Trade(
        user_id=current_user_id(),
        symbol=payload.symbol.strip().upper(),
        bucket=payload.bucket.strip() or "unassigned",
        side=payload.side,
        entry_price=payload.entry_price,
        stop_price=payload.stop_price,
        target_price=payload.target_price,
        exit_price=payload.exit_price,
        quantity=payload.quantity,
        fees=payload.fees,
        notes=payload.notes,
        status="closed" if is_closed else "open",
        opened_at=opened_at,
        closed_at=closed_at,
    )
    db.add(t)
    db.commit()
    return list_trades(db)


@router.put("/{trade_id}/close")
def close_trade(trade_id: int, payload: CloseIn, db: Session = Depends(get_db)) -> dict:
    t = db.get(Trade, trade_id)
    if t is None or t.user_id != current_user_id():
        raise HTTPException(status_code=404, detail="Trade not found")
    exit_at = _parse_date(payload.exit_date)
    if exit_at is None:
        raise HTTPException(status_code=400, detail="Exit date is required to close a trade.")
    if t.opened_at and exit_at < t.opened_at:
        raise HTTPException(status_code=400, detail="Exit date can't be before the entry date.")
    t.exit_price = payload.exit_price
    if payload.fees is not None:
        t.fees = payload.fees
    t.status = "closed"
    t.closed_at = exit_at
    db.commit()
    return list_trades(db)


@router.delete("/{trade_id}")
def delete_trade(trade_id: int, db: Session = Depends(get_db)) -> dict:
    t = db.get(Trade, trade_id)
    if t is None or t.user_id != current_user_id():
        raise HTTPException(status_code=404, detail="Trade not found")
    db.delete(t)
    db.commit()
    return list_trades(db)
