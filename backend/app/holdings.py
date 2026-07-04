"""Single source of truth for the user's holdings.

If the user has entered any positions (their real portfolio), those drive every
module. Otherwise we fall back to the provider's holdings — the sample CSV offline,
or the live broker feed in Angel mode — so a fresh install still has something to show.

Live LTP always comes from the market-data provider; when the provider has no price
(an offline symbol the user typed), we use their optional manual price, then cost.
"""

from __future__ import annotations

from sqlalchemy import select

from .core.config import settings
from .data import get_provider
from .data.provider import Holding
from .db import SessionLocal
from .models import Position


def _resolve_ltp(provider, p: Position) -> tuple[float, str]:
    """Pick the best available current price and say where it came from.

    Order: live market feed (Angel data-only) -> provider/CSV price -> the user's
    manual price -> cost.
    """
    from .market import get_market

    mkt = get_market()
    if mkt is not None:
        live = 0.0
        if p.token:
            live = mkt.ltp_by_token(p.exchange or "NSE", p.token)
        else:  # older equity rows have no token: resolve by symbol
            rec = mkt.resolve_equity(p.symbol)
            if rec:
                live = mkt.ltp_by_token(rec["exchange"], rec["token"])
        if live and live > 0:
            return live, "live"

    live = provider.get_ltp(p.symbol)
    if live and live > 0:
        return live, "live"
    if p.ltp and p.ltp > 0:
        return p.ltp, "manual"
    return p.avg_price, "cost"


def load_holdings() -> list[Holding]:
    """User positions (if any) with LTP filled in, else the provider's sample/live holdings."""
    provider = get_provider()
    db = SessionLocal()
    try:
        positions = list(
            db.scalars(select(Position).where(Position.user_id == settings.default_user_id))
        )
    finally:
        db.close()

    if not positions:
        return provider.get_holdings()

    # One batched live-price call for all holdings, instead of one per stock.
    from .market import get_market

    mkt = get_market()
    if mkt is not None:
        mkt.warm_positions(positions)

    holdings: list[Holding] = []
    for p in positions:
        ltp, _ = _resolve_ltp(provider, p)
        holdings.append(
            Holding(symbol=p.symbol, quantity=p.quantity, avg_price=p.avg_price, ltp=ltp,
                    bucket=p.bucket, side=getattr(p, "side", None) or "buy",
                    token=p.token, exchange=p.exchange, kind=p.kind or "EQ",
                    basket_id=getattr(p, "basket_id", None),
                    basket_label=getattr(p, "basket_label", None))
        )
    return holdings


def user_has_positions() -> bool:
    db = SessionLocal()
    try:
        return (
            db.scalar(
                select(Position).where(Position.user_id == settings.default_user_id).limit(1)
            )
            is not None
        )
    finally:
        db.close()
