"""Manual portfolio (positions) CRUD.

The user builds their real portfolio here: each holding is a symbol tagged to a
capital bucket with an avg buy price and quantity. These become the source of truth
for every module (see ``app.holdings.load_holdings``). Live LTP comes from the
provider; an optional manual price keeps P&L meaningful offline.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.disclaimers import with_disclaimer
from ..data import get_provider
from ..db import get_db
from ..holdings import _resolve_ltp, user_has_positions
from ..models import Position, Trade

router = APIRouter(prefix="/api/positions", tags=["positions"])


class PositionIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=32)
    bucket: str = Field(default="Long-term", max_length=64)
    quantity: float = Field(gt=0)                   # total units (lots x lot_size for F&O)
    avg_price: float = Field(gt=0)
    ltp: float | None = Field(default=None, ge=0)  # optional manual current price
    buy_date: str | None = None                    # ISO "YYYY-MM-DD"
    # Instrument details from the market-feed search (optional; absent for free-typed equity)
    tradingsymbol: str | None = None
    exchange: str | None = None
    token: str | None = None
    lot_size: int = Field(default=1, ge=1)
    kind: str = Field(default="EQ", max_length=8)  # EQ / FUT / CE / PE
    side: str = Field(default="buy", max_length=8)  # buy (long) | sell (short)
    # Set when this leg is part of a basket saved together (Basket Order page); legs
    # sharing a basket_id render as one grouped holding in the UI.
    basket_id: str | None = Field(default=None, max_length=36)
    basket_label: str | None = Field(default=None, max_length=64)


class PositionsBulkIn(BaseModel):
    positions: list[PositionIn]


class CloseHoldingIn(BaseModel):
    """Close a holding straight into the journal: sell it and log the realised trade."""
    exit_price: float = Field(gt=0)
    exit_date: str | None = None     # ISO date; defaults to today ("recorded as closing date")
    entry_date: str | None = None    # only used if the holding has no buy_date on file
    fees: float = Field(default=0.0, ge=0)
    quantity: float | None = Field(default=None, gt=0)  # sell only part (equity only); None = sell all


def _parse_date(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


# Angel F&O trading symbols embed the expiry as DDMONYY, e.g. RELIANCE30JUN261320CE,
# HDFCBANK28JUL26775PE, NIFTY28JUL26FUT.
_EXPIRY_RE = re.compile(r"(\d{2}[A-Z]{3}\d{2})")


def _fno_meta(tsym: str | None):
    """(expiry_date, strike, option_type) parsed from an Angel F&O tradingsymbol.

    e.g. RELIANCE30JUN261320CE -> (2026-06-30, 1320.0, "CE"); NIFTY28JUL26FUT ->
    (2026-07-28, None, None). strike/type are None for futures. Parsing the symbol
    (not the master) is what makes this work AFTER expiry, when the dead contract has
    been dropped from the live instrument master.
    """
    t = (tsym or "").upper()
    m = _EXPIRY_RE.search(t)
    if not m:
        return None, None, None
    try:
        exp = datetime.strptime(m.group(1), "%d%b%y").date()
    except ValueError:
        return None, None, None
    om = re.match(r"(\d+)(CE|PE)$", t[m.end():])
    if om:
        return exp, float(om.group(1)), om.group(2)
    return exp, None, None


def _expiry_of(p: Position, mkt):
    """Expiry date for an F&O holding, or None for equity. Parses the tradingsymbol
    (works post-expiry), falling back to a live master lookup by token."""
    if (getattr(p, "kind", "EQ") or "EQ") == "EQ":
        return None
    exp, _, _ = _fno_meta(getattr(p, "tradingsymbol", None))
    if exp is not None:
        return exp
    if mkt is not None:
        return mkt.expiry_date(getattr(p, "token", None))
    return None


def _row(p: Position, provider) -> dict:
    ltp, source = _resolve_ltp(provider, p)
    side = getattr(p, "side", None) or "buy"
    invested = p.quantity * p.avg_price
    value = p.quantity * ltp
    # Short legs (sold options/futures) profit when price falls.
    pnl = (value - invested) if side != "sell" else (invested - value)
    lot_size = p.lot_size or 1
    is_fno = (p.kind or "EQ") != "EQ"
    return {
        "id": p.id,
        "symbol": p.symbol,
        "tradingsymbol": p.tradingsymbol or p.symbol,
        "bucket": p.bucket,
        "quantity": p.quantity,
        "lot_size": lot_size,
        "lots": round(p.quantity / lot_size, 2) if is_fno and lot_size else None,
        "kind": p.kind or "EQ",
        "side": side,
        "basket_id": getattr(p, "basket_id", None),
        "basket_label": getattr(p, "basket_label", None),
        "exchange": p.exchange,
        "token": p.token,
        "avg_price": round(p.avg_price, 2),
        "ltp": round(ltp, 2),
        "price_source": source,  # live | manual | cost
        "invested": round(invested, 2),
        "current_value": round(value, 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round(pnl / invested * 100, 2) if invested else 0.0,
        "buy_date": p.buy_date.date().isoformat() if p.buy_date else None,
    }


def _list(db: Session, provider) -> dict:
    from ..market import get_market

    stmt = (
        select(Position)
        .where(Position.user_id == settings.default_user_id)
        .order_by(Position.bucket, Position.symbol)
    )
    positions = list(db.scalars(stmt))
    mkt = get_market()
    if mkt is not None:
        mkt.warm_positions(positions)  # one batched live-price call for the whole table
    rows = [_row(p, provider) for p in positions]
    return with_disclaimer({"positions": rows, "using_sample": len(rows) == 0})


@router.get("")
def list_positions(db: Session = Depends(get_db)) -> dict:
    return _list(db, get_provider())


def _make(payload: PositionIn) -> Position:
    return Position(
        user_id=settings.default_user_id,
        symbol=payload.symbol.strip().upper(),
        bucket=payload.bucket.strip() or "Long-term",
        quantity=payload.quantity,
        avg_price=payload.avg_price,
        ltp=payload.ltp,
        # Every holding gets an entry date — default to today if none was supplied, so the
        # journal always has it ready when the holding is later closed.
        buy_date=_parse_date(payload.buy_date) or datetime.combine(date.today(), datetime.min.time()),
        tradingsymbol=payload.tradingsymbol,
        exchange=payload.exchange,
        token=payload.token,
        lot_size=payload.lot_size or 1,
        kind=payload.kind or "EQ",
        side=payload.side or "buy",
        basket_id=payload.basket_id,
        basket_label=payload.basket_label,
    )


@router.post("")
def create_position(payload: PositionIn, db: Session = Depends(get_db)) -> dict:
    db.add(_make(payload))
    db.commit()
    return _list(db, get_provider())


@router.post("/bulk")
def create_positions(payload: PositionsBulkIn, db: Session = Depends(get_db)) -> dict:
    """Add several positions at once — e.g. saving a whole basket of legs to the portfolio."""
    for item in payload.positions:
        db.add(_make(item))
    db.commit()
    return _list(db, get_provider())


@router.get("/expiries")
def position_expiries(db: Session = Depends(get_db)) -> dict:
    """F&O holdings grouped by expiry status — for the day-before alert (read-only).

    ``expiring_soon`` = expires today or tomorrow (the "a day before" warning);
    ``expired`` = already past its expiry (these get auto-settled by settle-expired).
    """
    from ..market import get_market

    mkt = get_market()
    today = date.today()
    stmt = select(Position).where(Position.user_id == settings.default_user_id)
    expiring_soon, expired = [], []
    for p in db.scalars(stmt):
        exp = _expiry_of(p, mkt)
        if exp is None:
            continue
        days = (exp - today).days
        item = {
            "id": p.id,
            "symbol": p.symbol,
            "tradingsymbol": p.tradingsymbol or p.symbol,
            "kind": p.kind,
            "expiry": exp.isoformat(),
            "days_to_expiry": days,
        }
        if days < 0:
            expired.append(item)
        elif days <= 1:
            expiring_soon.append(item)
    return with_disclaimer(
        {"as_of": today.isoformat(), "expiring_soon": expiring_soon, "expired": expired}
    )


@router.post("/settle-expired")
def settle_expired(db: Session = Depends(get_db)) -> dict:
    """Auto-close every F&O holding whose contract has expired, into the journal.

    Fully automatic settlement (the user opted for this): exit price = **last traded
    price** (falls back to average cost if no live price is available, so an unpriced
    expired contract doesn't record a fake total loss). Each settled leg becomes a
    closed ``Trade`` and its position is removed — the same lifecycle as a manual
    close, but triggered by expiry rather than a click. Idempotent: once settled the
    position is gone, so re-calling settles nothing.
    """
    from ..market import get_market

    mkt = get_market()
    today = date.today()
    settled: list[dict] = []
    stmt = select(Position).where(Position.user_id == settings.default_user_id)
    for p in list(db.scalars(stmt)):
        exp = _expiry_of(p, mkt)
        if exp is None or exp >= today:
            continue
        # Settle at the contract's value AT EXPIRY: options at INTRINSIC
        # (max(0, spot-strike) for calls, max(0, strike-spot) for puts), futures at the
        # spot level. A dead option's own premium isn't retrievable from the live feed
        # (the token resolves to the UNDERLYING's price — a huge fake P&L), so intrinsic
        # from the underlying's current spot is the accurate figure. `fno_ref_price` is
        # the nearest-future LTP ~ spot. Falls back to a manual price, then cost, when
        # the spot is unavailable (offline), so P&L stays neutral rather than fake.
        _, strike, _ = _fno_meta(p.tradingsymbol)
        kind = (p.kind or "EQ").upper()
        spot = mkt.fno_ref_price(p.symbol) if mkt is not None else 0.0
        if kind in ("CE", "PE") and strike and spot and spot > 0:
            intrinsic = (spot - strike) if kind == "CE" else (strike - spot)
            exit_price, source = round(max(0.0, intrinsic), 2), "intrinsic"
        elif kind == "FUT" and spot and spot > 0:
            exit_price, source = round(spot, 2), "settlement"
        elif p.ltp and p.ltp > 0:
            exit_price, source = p.ltp, "manual"
        else:
            exit_price, source = p.avg_price, "cost"
        entry_at = p.buy_date or datetime.combine(exp, datetime.min.time())
        exit_at = datetime.combine(max(exp, entry_at.date()), datetime.min.time())
        side = "short" if (getattr(p, "side", "buy") or "buy") == "sell" else "long"
        db.add(Trade(
            user_id=settings.default_user_id,
            symbol=p.symbol,
            bucket=p.bucket,
            side=side,
            entry_price=p.avg_price,
            stop_price=p.avg_price,
            target_price=0.0,
            exit_price=exit_price,
            quantity=p.quantity,
            fees=0.0,
            status="closed",
            opened_at=entry_at,
            closed_at=exit_at,
            notes=f"Auto-settled at expiry ({exp.isoformat()})",
        ))
        settled.append({
            "id": p.id,
            "symbol": p.symbol,
            "tradingsymbol": p.tradingsymbol or p.symbol,
            "kind": p.kind,
            "expiry": exp.isoformat(),
            "exit_price": round(exit_price, 2),
            "price_source": source,
        })
        db.delete(p)
    if settled:
        db.commit()
    return with_disclaimer({"settled": settled, "count": len(settled)})


@router.post("/{position_id}/close")
def close_position(position_id: int, payload: CloseHoldingIn, db: Session = Depends(get_db)) -> dict:
    """Close a holding into the journal: log it as a realised ``Trade`` and drop the position.

    The journal and My Holdings are linked here — selling a holding from the portfolio
    records the trade automatically (entry = the buy date already on the holding, exit =
    today unless overridden) instead of re-typing it in the journal. The position is then
    removed (it's sold), so it stops counting as open capital and starts counting as a
    closed trade in the financial-year review.
    """
    p = db.get(Position, position_id)
    if p is None or p.user_id != settings.default_user_id:
        raise HTTPException(status_code=404, detail="Holding not found")

    entry_at = p.buy_date or _parse_date(payload.entry_date)
    if entry_at is None:
        raise HTTPException(
            status_code=400,
            detail="This holding has no buy date. Add the date you bought it (Edit), then close it.")
    exit_at = _parse_date(payload.exit_date) or datetime.combine(date.today(), datetime.min.time())
    if exit_at.date() < entry_at.date():
        raise HTTPException(status_code=400, detail="Exit date can't be before the buy date.")

    # Sell all, or just part of an equity holding (partial keeps the rest in My Holdings).
    sold_qty = payload.quantity if payload.quantity is not None else p.quantity
    if sold_qty <= 0 or sold_qty > p.quantity:
        raise HTTPException(status_code=400,
                            detail=f"Sell quantity must be between 0 and {p.quantity:g}.")
    partial = sold_qty < p.quantity
    if partial and ((p.kind or "EQ") != "EQ" or getattr(p, "basket_id", None)):
        raise HTTPException(
            status_code=400,
            detail="Partial close is only for Swing / Long-term equity — F&O and basket positions close in full.")

    # buy/sell holding -> long/short trade; no planned stop, so R-multiple is undefined.
    side = "short" if (getattr(p, "side", "buy") or "buy") == "sell" else "long"
    db.add(Trade(
        user_id=settings.default_user_id,
        symbol=p.symbol,
        bucket=p.bucket,
        side=side,
        entry_price=p.avg_price,
        stop_price=p.avg_price,
        target_price=0.0,
        exit_price=payload.exit_price,
        quantity=sold_qty,
        fees=payload.fees or 0.0,
        status="closed",
        opened_at=entry_at,
        closed_at=exit_at,
        notes="Closed from My Holdings" + (" (partial)" if partial else ""),
    ))
    if partial:
        p.quantity = p.quantity - sold_qty   # keep the rest at the same cost basis / buy date
    else:
        db.delete(p)
    db.commit()
    return _list(db, get_provider())


@router.put("/{position_id}")
def update_position(position_id: int, payload: PositionIn, db: Session = Depends(get_db)) -> dict:
    p = db.get(Position, position_id)
    if p is None or p.user_id != settings.default_user_id:
        raise HTTPException(status_code=404, detail="Position not found")
    p.symbol = payload.symbol.strip().upper()
    p.bucket = payload.bucket.strip() or "Long-term"
    p.quantity = payload.quantity
    p.avg_price = payload.avg_price
    p.ltp = payload.ltp
    p.buy_date = _parse_date(payload.buy_date) or datetime.combine(date.today(), datetime.min.time())
    p.tradingsymbol = payload.tradingsymbol
    p.exchange = payload.exchange
    p.token = payload.token
    p.lot_size = payload.lot_size or 1
    p.kind = payload.kind or "EQ"
    p.side = payload.side or "buy"
    db.commit()
    return _list(db, get_provider())


@router.delete("/{position_id}")
def delete_position(position_id: int, db: Session = Depends(get_db)) -> dict:
    p = db.get(Position, position_id)
    if p is None or p.user_id != settings.default_user_id:
        raise HTTPException(status_code=404, detail="Position not found")
    db.delete(p)
    db.commit()
    return _list(db, get_provider())
