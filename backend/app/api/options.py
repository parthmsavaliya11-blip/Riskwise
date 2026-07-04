"""Options strategy recommender endpoint.

Takes the user's view (bullish / bearish / neutral / volatile), conviction, budget
and expiry, prices a theoretical chain from spot + implied vol, then ranks the
strategy library by fit. All numbers come from ``services.options``.

Spot comes from the index's price history via the provider (or a ``spot`` override).
Implied vol defaults to a India-VIX-like level; in live mode the real chain premiums
and IV replace the theoretical ones with no change to the payoff/Greeks math.
"""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Query

from ..core.disclaimers import with_disclaimer
from ..data import get_provider
from ..services.options import INDEX_SPEC, recommend

router = APIRouter(prefix="/api", tags=["options"])

DEFAULT_SPOT = {"NIFTY": 23500.0, "BANKNIFTY": 51000.0, "SENSEX": 77000.0}


@router.get("/options")
def get_options(
    index: str = "NIFTY",
    view: str = Query("bullish", pattern="^(bullish|bearish|neutral|volatile)$"),
    conviction: str = Query("medium", pattern="^(low|medium|high)$"),
    budget: float | None = None,
    days_to_expiry: int = Query(30, ge=1, le=365),
    spot: float | None = None,
    iv: float | None = None,         # implied vol as a percent, e.g. 14 == 14%
    lot_size: int | None = None,
) -> dict:
    index_sym = index.strip().upper()
    spec = INDEX_SPEC.get(index_sym, {"step": 50, "lot_size": 50})
    step = spec["step"]
    lot = int(lot_size or spec["lot_size"])

    # Spot: explicit override, else last historical close, else a sane default.
    if spot is None:
        hist = get_provider().get_historical(
            index_sym, date.today() - timedelta(days=20), date.today()
        )
        spot = float(hist["close"].iloc[-1]) if not hist.empty else DEFAULT_SPOT.get(index_sym, 23500.0)

    sigma = (iv / 100.0) if iv is not None else 0.14  # ~India VIX level
    T = days_to_expiry / 365.0

    result = recommend(
        spot=spot, sigma=sigma, T=T, lot_size=lot, step=step,
        view=view, conviction=conviction, budget=budget,
    )

    return with_disclaimer(
        {
            "index": index_sym,
            "spot": round(spot, 2),
            "iv_pct": round(sigma * 100, 2),
            "days_to_expiry": days_to_expiry,
            "lot_size": lot,
            "strike_step": step,
            "view": view,
            "conviction": conviction,
            "budget": budget,
            **result,
        }
    )
