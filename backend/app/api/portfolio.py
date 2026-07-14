"""Portfolio endpoint: holdings with live value, P&L and per-bucket totals.

This proves the data pipe (provider -> API -> frontend) end-to-end and is the base
that Modules 1, 2 and 4 build on.
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter

from ..core.disclaimers import with_disclaimer
from ..holdings import load_holdings

router = APIRouter(prefix="/api", tags=["portfolio"])


@router.get("/portfolio")
def get_portfolio() -> dict:
    holdings = load_holdings()

    rows = []
    bucket_value: dict[str, float] = defaultdict(float)
    bucket_invested: dict[str, float] = defaultdict(float)
    total_value = 0.0
    total_invested = 0.0

    for h in holdings:
        # Leverage-aware capital view: for F&O `capital` is Angel's margin (not the full
        # contract value), so allocation % and % return reflect the money actually
        # deployed. Rupee P&L is unchanged. `notional`/`leverage` are exposed for display.
        rows.append(
            {
                "symbol": h.symbol,
                "quantity": h.quantity,
                "avg_price": round(h.avg_price, 2),
                "ltp": round(h.ltp, 2),
                "invested": round(h.capital, 2),
                "current_value": round(h.capital_value, 2),
                "pnl": round(h.pnl, 2),
                "pnl_pct": round(h.capital_pnl_pct, 2),
                "kind": h.kind,
                "margin": round(h.margin, 2) if h.margin is not None else None,
                "notional": round(h.current_value, 2),
                "leverage": round(h.leverage, 1) if h.leverage is not None else None,
                "bucket": h.bucket,
                "basket_id": h.basket_id,
                "basket_label": h.basket_label,
            }
        )
        bucket_value[h.bucket] += h.capital_value
        bucket_invested[h.bucket] += h.capital
        total_value += h.capital_value
        total_invested += h.capital

    buckets = [
        {
            "bucket": name,
            "current_value": round(val, 2),
            "invested": round(bucket_invested[name], 2),
            "allocation_pct": round(val / total_value * 100, 2) if total_value else 0.0,
        }
        for name, val in sorted(bucket_value.items())
    ]

    return with_disclaimer(
        {
            "holdings": rows,
            "buckets": buckets,
            "totals": {
                "invested": round(total_invested, 2),
                "current_value": round(total_value, 2),
                "pnl": round(total_value - total_invested, 2),
                "pnl_pct": round(
                    (total_value - total_invested) / total_invested * 100, 2
                )
                if total_invested
                else 0.0,
                "holdings_count": len(rows),
            },
        }
    )
