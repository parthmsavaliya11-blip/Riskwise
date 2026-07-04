"""F&O contract picker for the add-holding form.

A flat search box can't sensibly pick among thousands of option strikes, so the
F&O segment narrows step by step: choose a type (Futures / Call / Put), then an
underlying, then an expiry, then (for options) a strike. These endpoints feed each
step. ``kind=fut`` -> futures; ``kind=opt`` -> options (``right=CE|PE`` narrows the
side). Everything needs the live market feed (Angel, data-only); with it off these
return empty, since contract data only exists in the instrument master.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..market import get_market
from ..services.options import enrich_chain_greeks

router = APIRouter(prefix="/api/fno", tags=["fno"])


@router.get("/underlyings")
def fno_underlyings(q: str | None = None, kind: str = "fut", limit: int = 25) -> dict:
    mkt = get_market()
    if mkt is None:
        return {"live": False, "kind": kind, "underlyings": []}
    return {"live": True, "kind": kind, "underlyings": mkt.fno_underlyings(q, kind, limit)}


@router.get("/expiries")
def fno_expiries(name: str, kind: str = "fut") -> dict:
    mkt = get_market()
    if mkt is None:
        return {"live": False, "kind": kind, "expiries": []}
    return {"live": True, "kind": kind, "name": name.upper(), "expiries": mkt.fno_expiries(name, kind)}


@router.get("/future")
def fno_future(name: str, expiry: str | None = None) -> dict:
    mkt = get_market()
    if mkt is None:
        return {"live": False, "future": None}
    return {"live": True, "future": mkt.future_quote(name, expiry)}


@router.get("/chain")
def fno_chain(name: str, expiry: str, width: int = 12) -> dict:
    mkt = get_market()
    if mkt is None:
        return {"live": False, "name": name.upper(), "expiry": expiry, "rows": []}
    # OI + premium come from the feed; Greeks/IV are derived by the math engine.
    return {"live": True, **enrich_chain_greeks(mkt.option_chain(name, expiry, width))}


@router.get("/contracts")
def fno_contracts(name: str, kind: str = "fut", expiry: str | None = None,
                  right: str | None = None) -> dict:
    mkt = get_market()
    if mkt is None:
        return {"live": False, "kind": kind, "contracts": []}
    contracts = mkt.fno_contracts(name, kind, expiry, right)
    # For options, a live reference (nearest-future LTP) so the UI can mark ATM.
    ref_price = mkt.fno_ref_price(name) if kind == "opt" else 0.0
    return {"live": True, "kind": kind, "name": name.upper(), "expiry": expiry,
            "right": (right or "").upper() or None, "ref_price": ref_price,
            "contracts": contracts}
