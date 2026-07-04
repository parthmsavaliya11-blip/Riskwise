"""Beta-based portfolio hedge endpoint.

Pulls holdings + historical prices through the provider, computes each stock's beta
vs the chosen index, the value-weighted portfolio beta, and how many index-future
lots to short (plus a protective-put alternative). All numbers come from
``services.hedge``; this router just wires data in and shapes the response.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, Query

from ..core.disclaimers import with_disclaimer
from ..data import get_provider
from ..holdings import load_holdings
from .scope import scope_holdings
from ..services.hedge import (
    build_hedge_strategies,
    compute_beta,
    daily_returns,
    hedge_with_futures,
    hedge_with_puts,
    portfolio_beta,
)

router = APIRouter(prefix="/api", tags=["hedge"])

# Default F&O lot sizes (user-overridable; exchange revises these periodically).
INDEX_DEFAULTS = {"NIFTY": 50, "BANKNIFTY": 15, "SENSEX": 10}
# Strike interval per index (for the option-based hedge strategies).
INDEX_STEP = {"NIFTY": 50, "BANKNIFTY": 100, "SENSEX": 100}
# Below this many overlapping days a regression beta is too noisy to trust; we still
# show it but flag it low-confidence (a freshly listed contract has only a few days).
MIN_CONFIDENT_DAYS = 30


def _index_series(provider, mkt, index_sym, start, end, days):
    """Daily closes for the index — live Angel candles when the feed is on, else CSV.

    In live mode we stay on real candles only; mixing the synthetic sample CSV in for
    the index would make every stock's beta meaningless (it'd be regressed against the
    wrong series).
    """
    if mkt is not None:
        ref = mkt.index_ref(index_sym)
        if ref:
            s = mkt.candle_closes(ref[0], ref[1], days)
            if s is not None and not s.empty:
                return s
        return None  # live mode: no synthetic-CSV fallback for the index
    hist = provider.get_historical(index_sym, start, end)
    return hist["close"] if not hist.empty else None


def _holding_series(provider, mkt, h, start, end, days):
    """Daily closes for one holding.

    With the live feed on we use **only** real Angel candles, never the offline sample
    CSVs — those are synthetic fixtures uncorrelated with the live index, so regressing
    them against live index returns yields a meaningless near-zero beta. Equity and
    futures regress meaningfully and get their candles; options (CE/PE) are non-linear
    (premium is driven by theta/vega, not linearly by spot), so they get no regression
    beta and are flagged as assumed instead of a fabricated number.
    """
    kind = (getattr(h, "kind", None) or "EQ").upper()
    if mkt is not None:
        if kind in ("EQ", "FUT"):
            token = getattr(h, "token", None)
            exch = getattr(h, "exchange", None)
            if not token:  # older equity rows have no token: resolve by symbol
                rec = mkt.resolve_equity(h.symbol)
                if rec:
                    token, exch = rec["token"], rec["exchange"]
            if token:
                s = mkt.candle_closes(exch or "NSE", token, days)
                if s is not None and not s.empty:
                    return s
        return None  # live mode: no synthetic-CSV fallback
    # Offline mode: the sample CSVs are the intended data source.
    hist = provider.get_historical(h.symbol, start, end)
    return hist["close"] if not hist.empty else None


@router.get("/hedge")
def get_hedge(
    index: str = "NIFTY",
    index_price: float | None = None,
    lot_size: int | None = None,
    put_premium: float | None = None,
    iv: float | None = None,            # implied vol as a percent (e.g. 14 == 14%)
    days_to_expiry: int = Query(default=30, ge=1, le=365),
    bucket: str | None = None,          # scope to one capital bucket (else whole portfolio)
    lookback_days: int = Query(default=400, ge=30, le=2000),  # history window for beta
) -> dict:
    from ..market import get_market

    provider = get_provider()
    mkt = get_market()  # live Angel feed (data-only) when on; None offline
    holdings, available_buckets, scoped = scope_holdings(load_holdings(), bucket)
    index_sym = index.strip().upper()
    lot = int(lot_size or INDEX_DEFAULTS.get(index_sym, 50))

    end = date.today()
    start = end - timedelta(days=lookback_days)

    # Index series: real Angel candles when the feed is on (so each index regresses
    # differently), else the local CSV history.
    index_close = _index_series(provider, mkt, index_sym, start, end, lookback_days)
    if index_close is None or index_close.empty:
        return with_disclaimer(
            {
                "error": f"No price history for index {index_sym}. Add "
                f"data/history/{index_sym}.csv (date, close) or switch to live data.",
                "index": index_sym,
                "rows": [],
            }
        )

    # Regress each holding against the index PAIRWISE — on just the dates the two share
    # — so one short-history contract (e.g. a freshly listed future) doesn't truncate the
    # beta window for every other holding (which is what made all indices look the same
    # when most holdings fell back to an assumed beta on a tiny common window). We work
    # per holding (not via a symbol-keyed map) so an option leg can't accidentally inherit
    # the beta of an equity holding that shares its underlying's symbol.
    index_ret = daily_returns(index_close)

    total_value = sum(h.current_value for h in holdings)
    rows: list[dict] = []
    positions: list[dict] = []
    max_overlap = 0
    priced_count = 0
    for h in holdings:
        beta_res = None
        s = _holding_series(provider, mkt, h, start, end, lookback_days)
        if s is not None and not s.empty and len(index_ret) > 0:
            pair = daily_returns(s).rename("s").to_frame().join(
                index_ret.rename("x"), how="inner").dropna()
            if len(pair) >= 2:
                beta_res = compute_beta(pair["s"].to_numpy(), pair["x"].to_numpy())
                max_overlap = max(max_overlap, len(pair))
                priced_count += 1
        beta = beta_res["beta"] if beta_res else None
        n_days = beta_res["n"] if beta_res else 0
        weight = (h.current_value / total_value) if total_value else 0.0
        rows.append(
            {
                "symbol": h.symbol,
                "bucket": h.bucket,
                "value": round(h.current_value, 2),
                "weight_pct": round(weight * 100, 2),
                "beta": beta,
                "r_squared": beta_res["r_squared"] if beta_res else None,
                "n_days": n_days,
                "has_history": beta_res is not None,
                # Too few days to trust the slope — surfaced so the UI can flag it.
                "low_sample": beta_res is not None and n_days < MIN_CONFIDENT_DAYS,
                "beta_used": beta if beta is not None else 1.0,
            }
        )
        positions.append({"symbol": h.symbol, "value": h.current_value, "beta": beta})

    pb = portfolio_beta(positions)

    if index_price is None:
        index_price = float(index_close.iloc[-1])
    prem = put_premium if put_premium is not None else round(index_price * 0.01, 2)

    futures = hedge_with_futures(pb["total_value"], pb["portfolio_beta"], index_price, lot)
    puts = hedge_with_puts(pb["total_value"], pb["portfolio_beta"], index_price, lot, prem)

    # Full comparable hedging-strategy library, priced from spot + IV.
    sigma = (iv / 100.0) if iv is not None else 0.14
    T = max(days_to_expiry, 1) / 365.0
    step = INDEX_STEP.get(index_sym, 50)
    strategies = build_hedge_strategies(
        pb["total_value"], pb["portfolio_beta"], index_price, lot, sigma, T, step
    )

    missing = [r["symbol"] for r in rows if not r["has_history"]]

    return with_disclaimer(
        {
            "index": index_sym,
            "bucket": scoped,
            "available_buckets": available_buckets,
            "index_price": round(index_price, 2),
            "lot_size": lot,
            "iv_pct": round(sigma * 100, 2),
            "days_to_expiry": days_to_expiry,
            "portfolio_value": pb["total_value"],
            "portfolio_beta": pb["portfolio_beta"],
            "rows": rows,
            "hedge_futures": futures,
            "hedge_puts": puts,
            "hedge_strategies": strategies,
            "data_quality": {
                "priced_count": priced_count,
                "holdings_count": len(holdings),
                "aligned_days": int(max_overlap),
                "missing_history": missing,
                "assumed_beta_for_missing": 1.0,
                "history_source": "live" if mkt is not None else "csv",
            },
        }
    )
