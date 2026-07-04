"""Portfolio risk analytics endpoint.

Assembles holdings + price history into a portfolio equity curve and a returns
matrix, then runs concentration / correlation / VaR / drawdown / guardrail from
``services.risk``. All numbers come from those pure functions.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter

from ..core.disclaimers import with_disclaimer
from ..data import get_provider
from ..data.symbols import SECTOR_MAP
from ..holdings import load_holdings
from .scope import scope_holdings
from ..services.risk import (
    concentration,
    correlation_matrix,
    daily_loss_guardrail,
    drawdown,
    value_at_risk,
)

router = APIRouter(prefix="/api", tags=["risk"])


@router.get("/risk")
def get_risk(
    confidence: int = 95,
    daily_loss_limit: float | None = None,
    day_pnl: float | None = None,
    bucket: str | None = None,          # scope to one capital bucket (else whole portfolio)
    lookback_days: int = 400,
) -> dict:
    provider = get_provider()
    holdings, available_buckets, scoped = scope_holdings(load_holdings(), bucket)

    positions = [{"symbol": h.symbol, "value": h.current_value} for h in holdings]
    total_value = sum(h.current_value for h in holdings)
    conc = concentration(positions, sector_map=SECTOR_MAP)

    # Build aligned close-price frame for the holdings that have history.
    end = date.today()
    start = end - timedelta(days=lookback_days)
    qty = {h.symbol: h.quantity for h in holdings}
    closes: dict[str, pd.Series] = {}
    for h in holdings:
        hist = provider.get_historical(h.symbol, start, end)
        if not hist.empty:
            closes[h.symbol] = hist["close"]

    corr = {"symbols": [], "matrix": [], "high_pairs": []}
    var = {"available": False}
    dd = {"available": False}
    guard = {"configured": False}

    if closes:
        price_df = pd.DataFrame(closes).dropna()
        if not price_df.empty:
            returns_df = price_df.pct_change().dropna()
            corr = correlation_matrix(returns_df)

            # Portfolio equity curve = sum_i (qty_i * close_i(t)).
            weights = pd.Series({s: qty[s] for s in price_df.columns})
            equity = (price_df * weights).sum(axis=1)
            port_returns = equity.pct_change().dropna().to_numpy()

            var = value_at_risk(port_returns, total_value or float(equity.iloc[-1]), confidence)
            dd = drawdown(equity)

            # Default "today's P&L" = the last day's change in the equity curve.
            if day_pnl is None and len(equity) >= 2:
                day_pnl = float(equity.iloc[-1] - equity.iloc[-2])

    if daily_loss_limit is not None:
        guard = daily_loss_guardrail(day_pnl if day_pnl is not None else 0.0, daily_loss_limit)

    return with_disclaimer(
        {
            "bucket": scoped,
            "available_buckets": available_buckets,
            "total_value": round(total_value, 2),
            "concentration": conc,
            "correlation": corr,
            "var": var,
            "drawdown": dd,
            "guardrail": guard,
            "day_pnl": None if day_pnl is None else round(day_pnl, 2),
        }
    )
