"""Portfolio risk analytics — pure, auditable math.

  * Concentration: top-N weights, single-stock %, sector exposure, Herfindahl index.
  * Correlation: pairwise correlation of daily returns; flags clusters that move together.
  * Value at Risk: 1-day historical + parametric (normal) VaR, plus CVaR (expected
    shortfall) — "on a bad day you can lose about Rs X".
  * Drawdown: current and max drawdown from the portfolio equity curve.
  * Daily-loss guardrail: a behavioural circuit-breaker vs a user-set daily loss cap.

Inputs are plain arrays / DataFrames; callers (the API) assemble them from the provider.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Z-scores for the left tail at common confidence levels (parametric VaR).
_Z = {90: 1.2816, 95: 1.6449, 99: 2.3263}

# Sector tags for the known sample symbols; unknown -> "Other".
SECTOR_MAP = {
    "RELIANCE": "Energy",
    "HDFCBANK": "Financials",
    "ICICIBANK": "Financials",
    "TCS": "IT",
    "INFY": "IT",
    "TATAMOTORS": "Auto",
    "NIFTY24JUNFUT": "Index",
}


def concentration(positions: list[dict], sector_map: dict[str, str] | None = None) -> dict:
    """Top-N weights, sector exposure and a Herfindahl concentration index.

    ``positions``: dicts with ``symbol`` and ``value``.
    """
    sector_map = sector_map or SECTOR_MAP
    total = sum(p["value"] for p in positions)
    if total <= 0:
        return {"total_value": 0.0, "holdings": [], "sectors": [], "hhi": 0.0, "flags": []}

    ranked = sorted(positions, key=lambda p: p["value"], reverse=True)
    holdings = [
        {"symbol": p["symbol"], "value": round(p["value"], 2),
         "weight_pct": round(p["value"] / total * 100, 2)}
        for p in ranked
    ]

    fractions = [p["value"] / total for p in ranked]
    hhi = round(sum(f * f for f in fractions), 4)  # 0 (diverse) .. 1 (one bet)

    sector_value: dict[str, float] = {}
    for p in positions:
        sec = sector_map.get(p["symbol"], "Other")
        sector_value[sec] = sector_value.get(sec, 0.0) + p["value"]
    sectors = sorted(
        ({"sector": s, "value": round(v, 2), "weight_pct": round(v / total * 100, 2)}
         for s, v in sector_value.items()),
        key=lambda x: x["value"], reverse=True,
    )

    flags = []
    if holdings and holdings[0]["weight_pct"] > 25:
        flags.append(f"{holdings[0]['symbol']} is {holdings[0]['weight_pct']}% of the portfolio (single-stock concentration).")
    top3 = round(sum(h["weight_pct"] for h in holdings[:3]), 2)
    if top3 > 60:
        flags.append(f"Top 3 holdings are {top3}% of the portfolio.")
    if sectors and sectors[0]["weight_pct"] > 40:
        flags.append(f"{sectors[0]['weight_pct']}% is in {sectors[0]['sector']} — limited sector diversification.")

    return {
        "total_value": round(total, 2),
        "holdings": holdings,
        "sectors": sectors,
        "top1_pct": holdings[0]["weight_pct"] if holdings else 0.0,
        "top3_pct": top3,
        "hhi": hhi,
        "flags": flags,
    }


def correlation_matrix(returns: pd.DataFrame, threshold: float = 0.7) -> dict:
    """Correlation of daily returns + highlighted high-correlation pairs."""
    if returns.shape[1] < 2 or returns.empty:
        return {"symbols": list(returns.columns), "matrix": [], "high_pairs": []}
    corr = returns.corr()
    symbols = list(corr.columns)
    matrix = [[round(float(corr.iloc[i, j]), 2) for j in range(len(symbols))]
              for i in range(len(symbols))]
    high_pairs = []
    for i in range(len(symbols)):
        for j in range(i + 1, len(symbols)):
            c = float(corr.iloc[i, j])
            if c >= threshold:
                high_pairs.append({"a": symbols[i], "b": symbols[j], "corr": round(c, 2)})
    high_pairs.sort(key=lambda p: p["corr"], reverse=True)
    return {"symbols": symbols, "matrix": matrix, "high_pairs": high_pairs}


def value_at_risk(port_returns: np.ndarray, portfolio_value: float, confidence: int = 95) -> dict:
    """1-day VaR (historical + parametric) and CVaR, as rupees and % of portfolio."""
    r = np.asarray(port_returns, dtype=float)
    r = r[~np.isnan(r)]
    if len(r) < 2 or portfolio_value <= 0:
        return {"confidence": confidence, "horizon_days": 1, "available": False}

    tail = 100 - confidence
    hist_q = float(np.percentile(r, tail))          # e.g. 5th percentile (a negative return)
    hist_var = max(-hist_q, 0.0) * portfolio_value

    mu, sigma = float(np.mean(r)), float(np.std(r))
    z = _Z.get(confidence, 1.6449)
    param_loss_ret = z * sigma - mu                 # worst expected loss return at conf
    param_var = max(param_loss_ret, 0.0) * portfolio_value

    below = r[r <= hist_q]
    cvar_ret = float(np.mean(below)) if below.size else hist_q
    cvar = max(-cvar_ret, 0.0) * portfolio_value

    return {
        "confidence": confidence,
        "horizon_days": 1,
        "available": True,
        "historical_var": round(hist_var, 2),
        "historical_var_pct": round(hist_var / portfolio_value * 100, 2),
        "parametric_var": round(param_var, 2),
        "parametric_var_pct": round(param_var / portfolio_value * 100, 2),
        "cvar": round(cvar, 2),
        "cvar_pct": round(cvar / portfolio_value * 100, 2),
        "daily_vol_pct": round(sigma * 100, 2),
        "n_days": int(len(r)),
    }


def drawdown(equity: pd.Series) -> dict:
    """Current and max drawdown from a portfolio equity curve."""
    if equity is None or len(equity) < 2:
        return {"available": False}
    values = equity.astype(float)
    running_peak = values.cummax()
    dd = (values - running_peak) / running_peak  # <= 0
    max_dd = float(dd.min())
    trough_idx = dd.idxmin()
    current_dd = float(dd.iloc[-1])

    series = [
        {"date": str(idx.date()) if hasattr(idx, "date") else str(idx),
         "value": round(float(v), 2),
         "drawdown_pct": round(float(d) * 100, 2)}
        for idx, v, d in zip(values.index, values.values, dd.values)
    ]
    return {
        "available": True,
        "current_drawdown_pct": round(current_dd * 100, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "peak_value": round(float(running_peak.iloc[-1]), 2),
        "trough_date": str(trough_idx.date()) if hasattr(trough_idx, "date") else str(trough_idx),
        "current_value": round(float(values.iloc[-1]), 2),
        "series": series,
    }


def daily_loss_guardrail(day_pnl: float, limit_amount: float) -> dict:
    """Status of today's mark-to-market loss vs the user's daily loss cap."""
    if limit_amount is None or limit_amount <= 0:
        return {"configured": False}
    loss = max(-day_pnl, 0.0)  # only losses count toward the cap
    used_pct = loss / limit_amount * 100
    if loss >= limit_amount:
        status = "breached"
    elif used_pct >= 80:
        status = "approaching"
    else:
        status = "ok"
    return {
        "configured": True,
        "day_pnl": round(day_pnl, 2),
        "limit_amount": round(limit_amount, 2),
        "loss_so_far": round(loss, 2),
        "used_pct": round(used_pct, 1),
        "remaining": round(max(limit_amount - loss, 0.0), 2),
        "status": status,
    }
