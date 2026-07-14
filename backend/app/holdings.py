"""Single source of truth for the user's holdings.

If the user has entered any positions (their real portfolio), those drive every
module. Otherwise we fall back to the provider's holdings — the sample CSV offline,
or the live broker feed in Angel mode — so a fresh install still has something to show.

Live LTP always comes from the market-data provider; when the provider has no price
(an offline symbol the user typed), we use their optional manual price, then cost.
"""

from __future__ import annotations

from sqlalchemy import select

from .auth.context import current_user_id
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


def resolve_fno_margins(legs: list[dict], mkt) -> dict:
    """Real Angel SPAN+exposure margin per F&O leg, keyed by each leg's ``key``.

    F&O is leveraged — the capital deployed is the margin the exchange blocks, not the
    full contract value. We ask Angel's batch calculator (``basket_margin_total``):
      * legs saved as ONE basket (same ``basket_id``) are netted together, so the hedge
        benefit is reflected (a hedged basket blocks far less than its naked legs), then
        the netted total is split across those legs by notional weight (display only —
        the group renders as one holding anyway);
      * each standalone F&O leg is priced on its own (no netting between unrelated trades,
        which is the conservative, interpretable choice).
    Equity legs and anything without a token/live-feed get no margin (caller falls back
    to notional). Returns ``{key: margin}`` only for legs we could price.
    """
    if mkt is None:
        return {}
    fno = [l for l in legs if (l.get("kind") or "EQ") != "EQ" and l.get("token")]
    if not fno:
        return {}

    groups: dict[object, list[dict]] = {}
    for l in fno:
        gid = l.get("basket_id") or ("__solo__", l["key"])  # standalone legs group alone
        groups.setdefault(gid, []).append(l)

    out: dict = {}
    for members in groups.values():
        pos = [
            {"token": l["token"], "exchange": l.get("exchange") or "NFO",
             "qty": int(l["qty"]), "price": float(l.get("price") or 0),
             "tradeType": "SELL" if (l.get("side") or "buy") == "sell" else "BUY"}
            for l in members
        ]
        total = mkt.basket_margin_total(pos)
        if total is None:
            continue  # leave these legs unmargined -> caller uses notional
        weights = [abs(float(l["qty"]) * float(l.get("price") or 0)) for l in members]
        wsum = sum(weights)
        for l, w in zip(members, weights):
            out[l["key"]] = total * (w / wsum) if wsum else total / len(members)
    return out


def _apply_holding_margins(holdings: list[Holding], mkt) -> None:
    """Fill in each F&O holding's Angel margin (leverage-aware capital)."""
    legs = [
        {"key": i, "token": h.token, "exchange": h.exchange, "qty": h.quantity,
         "price": h.ltp, "side": h.side, "kind": h.kind, "basket_id": h.basket_id}
        for i, h in enumerate(holdings)
    ]
    margins = resolve_fno_margins(legs, mkt)
    for i, h in enumerate(holdings):
        if i in margins:
            h.margin = round(margins[i], 2)


def load_holdings() -> list[Holding]:
    """User positions (if any) with LTP filled in, else the provider's sample/live holdings."""
    provider = get_provider()
    db = SessionLocal()
    try:
        positions = list(
            db.scalars(select(Position).where(Position.user_id == current_user_id()))
        )
    finally:
        db.close()

    if not positions:
        # A signed-in user with no holdings starts empty; only the offline / no-auth
        # context (verify scripts, startup warm-up) falls back to the sample portfolio.
        if current_user_id() == settings.default_user_id:
            return provider.get_holdings()
        return []

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
    # F&O leverage: attach the real Angel margin so capital/allocation/return are
    # leverage-aware (falls back to notional for anything the feed can't price).
    if mkt is not None:
        _apply_holding_margins(holdings, mkt)
    return holdings


def user_has_positions() -> bool:
    db = SessionLocal()
    try:
        return (
            db.scalar(
                select(Position).where(Position.user_id == current_user_id()).limit(1)
            )
            is not None
        )
    finally:
        db.close()
