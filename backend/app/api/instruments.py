"""Instrument search for the add-holding form.

With the market feed on (Angel, data-only), this searches the full NSE+BSE universe:
``kind=equity`` returns stocks, ``kind=fno`` returns futures/option contracts with
their lot sizes. With the feed off, it falls back to the offline curated stock list.
"""

from __future__ import annotations

from fastapi import APIRouter

from ..data.symbols import search_symbols
from ..market import get_market

router = APIRouter(prefix="/api", tags=["instruments"])


@router.get("/instruments")
def get_instruments(q: str | None = None, kind: str = "equity", limit: int = 25) -> dict:
    mkt = get_market()
    if mkt is None:
        # Offline: curated stocks only, shaped like the live results.
        if kind == "fno":
            return {"live": False, "kind": kind, "instruments": []}
        rows = [
            {"symbol": s["symbol"], "name": s["name"], "exchange": "NSE",
             "token": None, "lot_size": 1, "kind": "EQ"}
            for s in search_symbols(q, limit)
        ]
        return {"live": False, "kind": kind, "instruments": rows}

    if kind == "fno":
        return {"live": True, "kind": kind, "instruments": mkt.search_fno(q, limit)}
    return {"live": True, "kind": kind, "instruments": mkt.search_equity(q, limit)}
