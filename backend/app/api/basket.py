"""Basket order analysis.

The user builds a basket of legs (index/stock futures + options, picked from the
live option chain) and gets a combined payoff, max P/L, breakevens and net Greeks.
This is **analysis only** — consistent with the read-only broker design, the app never
places the order; the user takes the basket to their broker.

Every number is computed by ``services.options`` (deterministic). The AI layer only
narrates these figures via ``/api/ai/explain`` with module="basket".
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..core.disclaimers import with_disclaimer
from ..market import get_market
from ..services.options import Leg, analyze_basket

router = APIRouter(prefix="/api/basket", tags=["basket"])


class BasketLeg(BaseModel):
    type: str                         # future | call | put  (CE/PE accepted too)
    side: str = "buy"                 # buy | sell
    lots: int = Field(gt=0)
    strike: float | None = None       # required for options
    price: float = Field(ge=0)        # option premium, or futures entry price
    token: str | None = None          # live instrument token (for the margin calc)
    exchange: str | None = None       # NFO / BFO


class BasketRequest(BaseModel):
    name: str
    expiry: str | None = None         # e.g. "28JUL2026" -> time to expiry
    lot_size: int = Field(gt=0)
    spot: float | None = None         # live forward; resolved from feed if absent
    iv: float | None = None           # fallback IV (percent) for legs we can't solve
    legs: list[BasketLeg] = []


def _days_to_expiry(expiry: str | None) -> int:
    if not expiry:
        return 30
    try:
        d = datetime.strptime(expiry, "%d%b%Y").date()
        return max((d - date.today()).days, 1)
    except (ValueError, TypeError):
        return 30


_KIND = {"future": "underlying", "fut": "underlying", "call": "call", "ce": "call",
         "put": "put", "pe": "put"}


@router.post("/analyse")
def analyse_basket(req: BasketRequest) -> dict:
    mkt = get_market()
    spot = req.spot
    if spot is None and mkt is not None:
        spot = mkt.fno_ref_price(req.name) or None

    engine_legs: list[Leg] = []
    for lg in req.legs:
        kind = _KIND.get(lg.type.strip().lower())
        if kind is None:
            continue
        sign = 1 if lg.side.strip().lower() != "sell" else -1
        qty = sign * lg.lots
        if kind == "underlying":
            # A future: worth spot at expiry, "bought" at its entry price.
            engine_legs.append(Leg("underlying", round(lg.price, 2), qty, round(lg.price, 2)))
        else:
            engine_legs.append(Leg(kind, float(lg.strike or 0), qty, round(lg.price, 2)))

    if not engine_legs:
        return with_disclaimer({"error": "Add at least one leg to analyse.", "legs": []})

    # Fall back for spot: average option strike, else first future entry.
    if not spot:
        opt_strikes = [l.strike for l in engine_legs if l.kind != "underlying"]
        fut = [l.strike for l in engine_legs if l.kind == "underlying"]
        spot = (sum(opt_strikes) / len(opt_strikes)) if opt_strikes else (fut[0] if fut else 0.0)

    T = _days_to_expiry(req.expiry) / 365.0
    default_sigma = (req.iv / 100.0) if req.iv else 0.18

    result = analyze_basket(engine_legs, float(spot), req.lot_size, T, default_sigma)
    margin = _margins(mkt, req)
    return with_disclaimer({
        "name": req.name.upper(), "expiry": req.expiry,
        "days_to_expiry": _days_to_expiry(req.expiry), **result, **margin,
    })


def _margins(mkt, req: BasketRequest) -> dict:
    """Live SPAN+exposure margin for the basket (and the 'unhedged' version for contrast).

    The exchange nets hedge benefit across legs, so the full basket needs far less than
    its risk legs alone (e.g. a naked future). ``margin_unhedged`` drops the long-option
    hedges to show that saving. All None when the feed/tokens are unavailable.
    """
    # Gross notional (full contract value of every leg) — the leverage numerator, and a
    # feed-independent figure so we can always show how much less than notional you deploy.
    gross_notional = round(sum(lg.lots * req.lot_size * lg.price for lg in req.legs), 2)

    if mkt is None:
        return {"margin_required": None, "margin_unhedged": None, "margin_saved": None,
                "notional": gross_notional, "leverage": None}

    def to_pos(lg: BasketLeg) -> dict | None:
        if not lg.token:
            return None
        return {"token": lg.token, "exchange": lg.exchange or "NFO",
                "qty": lg.lots * req.lot_size, "price": lg.price,
                "tradeType": "SELL" if lg.side.strip().lower() == "sell" else "BUY"}

    all_pos = [p for p in (to_pos(l) for l in req.legs) if p]
    if not all_pos:
        return {"margin_required": None, "margin_unhedged": None, "margin_saved": None,
                "notional": gross_notional, "leverage": None}

    full = mkt.basket_margin(all_pos)
    margin_required = (full or {}).get("totalMarginRequired")
    # Leverage = full contract value / capital you actually block.
    leverage = (round(gross_notional / margin_required, 1)
                if margin_required and gross_notional else None)

    # "Unhedged" = the margin-consuming legs only (futures + short options), i.e. drop the
    # long-option hedges. Only meaningful when there IS a hedge to remove.
    is_hedge = lambda l: l.type.lower() in ("call", "put", "ce", "pe") and l.side.lower() != "sell"
    risk_legs = [l for l in req.legs if not is_hedge(l)]
    margin_unhedged = margin_saved = None
    if any(is_hedge(l) for l in req.legs) and risk_legs:
        risk_pos = [p for p in (to_pos(l) for l in risk_legs) if p]
        unhedged = mkt.basket_margin(risk_pos) if risk_pos else None
        margin_unhedged = (unhedged or {}).get("totalMarginRequired")
        if margin_required is not None and margin_unhedged is not None:
            margin_saved = round(margin_unhedged - margin_required, 2)

    return {"margin_required": margin_required, "margin_unhedged": margin_unhedged,
            "margin_saved": margin_saved, "notional": gross_notional, "leverage": leverage}
