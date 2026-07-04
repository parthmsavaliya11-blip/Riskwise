"""Beta-based portfolio hedge — pure, auditable math.

Beta measures how much a stock moves for a 1% move in the index. We regress each
stock's daily returns on the index's daily returns; the slope is beta and R^2 says
how well the index explains the stock (low R^2 => beta is not very meaningful).

    beta_i      = Cov(stock_i, index) / Var(index)         (slope of the regression)
    R^2         = corr(stock_i, index) ** 2
    portfolio_beta = sum_i ( weight_i * beta_i )            (weight = value / total)

Hedge with index futures (short to neutralise market risk):

    beta_adjusted_exposure = portfolio_value * portfolio_beta
    lots_to_short          = round( beta_adjusted_exposure / (index_price * lot_size) )

We compute the slope directly from covariance/variance with numpy (no scipy
dependency, which keeps Python 3.14 wheel resolution simple).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Reuse the options module's Black-Scholes pricer (math.erf, no scipy) so every
# option-based hedge's cost is priced consistently with the Options module.
from .options import bs_price


def daily_returns(closes: pd.Series) -> pd.Series:
    """Simple daily returns from a close-price series, NaNs dropped."""
    return closes.astype(float).pct_change().dropna()


def aligned_returns(close_by_symbol: dict[str, pd.Series]) -> pd.DataFrame:
    """Return a DataFrame of daily returns aligned on the dates all series share.

    Beta is only meaningful on overlapping dates, so we inner-join (dropna) the
    per-symbol return columns.
    """
    cols = {sym: daily_returns(s) for sym, s in close_by_symbol.items() if s is not None}
    if not cols:
        return pd.DataFrame()
    return pd.DataFrame(cols).dropna()


def compute_beta(stock_returns, index_returns) -> dict | None:
    """Beta, alpha and R^2 of stock vs index. None if there isn't enough data."""
    s = np.asarray(stock_returns, dtype=float)
    x = np.asarray(index_returns, dtype=float)
    n = int(min(len(s), len(x)))
    if n < 2:
        return None
    s, x = s[:n], x[:n]
    var_x = float(np.var(x))  # population variance
    if var_x == 0:
        return None
    cov = float(np.cov(s, x, bias=True)[0, 1])
    beta = cov / var_x
    alpha = float(s.mean() - beta * x.mean())
    corr = float(np.corrcoef(s, x)[0, 1]) if n >= 2 else 0.0
    r_squared = 0.0 if np.isnan(corr) else corr * corr
    return {
        "beta": round(beta, 4),
        "alpha": round(alpha, 6),
        "r_squared": round(r_squared, 4),
        "n": n,
    }


def portfolio_beta(positions: list[dict]) -> dict:
    """Value-weighted portfolio beta.

    ``positions``: dicts with ``value`` and ``beta`` (beta may be None if unknown,
    in which case the position is still weighted but contributes its assumed beta).
    """
    total_value = sum(p["value"] for p in positions)
    if total_value <= 0:
        return {"portfolio_beta": 0.0, "total_value": 0.0, "weights": []}

    weighted = 0.0
    weights = []
    for p in positions:
        w = p["value"] / total_value
        beta = p.get("beta")
        beta = 1.0 if beta is None else beta  # conservative fallback: assume market beta
        weighted += w * beta
        weights.append({"symbol": p.get("symbol"), "weight": round(w, 4)})

    return {
        "portfolio_beta": round(weighted, 4),
        "total_value": round(total_value, 2),
        "weights": weights,
    }


def hedge_with_futures(
    portfolio_value: float,
    port_beta: float,
    index_price: float,
    lot_size: int,
) -> dict:
    """How many index-future lots to short to neutralise market risk."""
    beta_adjusted_exposure = portfolio_value * port_beta
    contract_value = index_price * lot_size
    if contract_value <= 0:
        return {"error": "Index price and lot size must be positive."}

    lots_exact = beta_adjusted_exposure / contract_value
    lots_to_short = round(lots_exact)
    hedged_notional = lots_to_short * contract_value
    residual_exposure = beta_adjusted_exposure - hedged_notional
    residual_beta = residual_exposure / portfolio_value if portfolio_value else 0.0

    return {
        "beta_adjusted_exposure": round(beta_adjusted_exposure, 2),
        "contract_value": round(contract_value, 2),
        "lots_exact": round(lots_exact, 3),
        "lots_to_short": lots_to_short,
        "hedged_notional": round(hedged_notional, 2),
        "residual_exposure": round(residual_exposure, 2),
        "residual_beta": round(residual_beta, 4),
    }


def hedge_with_puts(
    portfolio_value: float,
    port_beta: float,
    index_price: float,
    lot_size: int,
    put_premium: float,
) -> dict:
    """Protective ATM index puts as an alternative hedge, with estimated cost.

    Uses the same beta-adjusted contract count as the futures hedge. ``put_premium``
    is the per-unit ATM put price (from the chain in live mode, or a user estimate);
    the full option chain + Greeks arrive in Module 3.
    """
    contract_value = index_price * lot_size
    if contract_value <= 0:
        return {"error": "Index price and lot size must be positive."}

    beta_adjusted_exposure = portfolio_value * port_beta
    put_lots = round(beta_adjusted_exposure / contract_value)
    est_cost = put_lots * lot_size * max(put_premium, 0.0)
    cost_pct = (est_cost / portfolio_value * 100.0) if portfolio_value else 0.0

    return {
        "put_lots": put_lots,
        "strike_atm": round(index_price, 2),
        "put_premium": round(put_premium, 2),
        "est_cost": round(est_cost, 2),
        "cost_pct_of_portfolio": round(cost_pct, 2),
    }


# --------------------------------------------------------------------------- #
# Full hedging-strategy library
# --------------------------------------------------------------------------- #
# The market/textbook ways to hedge an equity portfolio with index instruments.
# Each is sized to the same beta-adjusted exposure as the futures hedge, and its
# cost is priced with Black-Scholes from spot + IV (theoretical chain offline; real
# chain in live mode). Every entry says what it protects and what you give up.

def _round_step(x: float, step: int) -> float:
    return round(x / step) * step


def _zero_cost_call_strike(spot: float, T: float, sigma: float, target_premium: float,
                           step: int, start: float) -> float:
    """Lowest call strike whose premium <= target (for a ~zero-cost collar)."""
    K = start
    for _ in range(80):
        if bs_price("call", spot, K, T, sigma) <= target_premium:
            return K
        K += step
    return K


def build_hedge_strategies(
    portfolio_value: float,
    port_beta: float,
    index_price: float,
    lot_size: int,
    sigma: float,
    T: float,
    step: int,
    otm_pct: float = 5.0,
) -> dict:
    """Return the comparable hedging-strategy library, sized + priced.

    ``sigma`` is implied vol as a decimal (0.14 = 14%); ``T`` is years to expiry;
    ``step`` is the strike interval; ``otm_pct`` is how far OTM the protective put /
    short call sit.
    """
    S = float(index_price)
    contract_value = S * lot_size
    if contract_value <= 0 or portfolio_value <= 0:
        return {"lots": 0, "strategies": []}

    exposure = portfolio_value * port_beta
    lots = round(exposure / contract_value)
    units = lots * lot_size  # option/future units behind `lots` lots

    atm = _round_step(S, step)
    put_otm = _round_step(S * (1 - otm_pct / 100.0), step)
    call_otm = _round_step(S * (1 + otm_pct / 100.0), step)

    p_atm = bs_price("put", S, atm, T, sigma)
    p_otm = bs_price("put", S, put_otm, T, sigma)
    c_otm = bs_price("call", S, call_otm, T, sigma)

    def pct(cost: float) -> float:
        return round(cost / portfolio_value * 100.0, 2)

    def money(per_unit: float) -> float:
        return round(units * per_unit, 2)

    strategies: list[dict] = []

    # 1. Short index futures — full, symmetric beta hedge.
    strategies.append({
        "key": "short_futures",
        "name": "Short Index Futures",
        "instrument": f"Sell {lots} lot(s) of futures",
        "legs": [{"action": "Sell", "type": "future", "strike": None, "lots": lots}],
        "net_cost": 0.0, "net_type": "margin", "cost_pct": 0.0,
        "floor": None, "cap": None,
        "protects": "Neutralises the whole beta-adjusted market exposure.",
        "tradeoff": "Gives up the upside too — you go flat to the market. Needs margin and daily mark-to-market.",
    })

    # 2. Protective put (ATM) — insurance, keeps upside.
    strategies.append({
        "key": "protective_put_atm",
        "name": "Protective Put (ATM)",
        "instrument": f"Buy {lots} lot(s) of {atm:.0f} put",
        "legs": [{"action": "Buy", "type": "put", "strike": atm, "premium": round(p_atm, 2), "lots": lots}],
        "net_cost": money(p_atm), "net_type": "debit", "cost_pct": pct(money(p_atm)),
        "floor": atm, "cap": None,
        "protects": "Caps the downside at the strike while keeping the full upside.",
        "tradeoff": "The premium is a sunk cost (a 'deductible') if the market doesn't fall.",
    })

    # 3. Protective put (OTM) — cheaper, with a deductible.
    strategies.append({
        "key": "protective_put_otm",
        "name": f"Protective Put ({otm_pct:.0f}% OTM)",
        "instrument": f"Buy {lots} lot(s) of {put_otm:.0f} put",
        "legs": [{"action": "Buy", "type": "put", "strike": put_otm, "premium": round(p_otm, 2), "lots": lots}],
        "net_cost": money(p_otm), "net_type": "debit", "cost_pct": pct(money(p_otm)),
        "floor": put_otm, "cap": None,
        "protects": "Cheaper downside cover below the OTM strike; keeps upside.",
        "tradeoff": f"The first ~{otm_pct:.0f}% fall (down to the strike) is unprotected.",
    })

    # 4. Collar — buy OTM put, sell OTM call to fund it.
    collar_net = p_otm - c_otm
    strategies.append({
        "key": "collar",
        "name": "Protective Collar",
        "instrument": f"Buy {put_otm:.0f} put + Sell {call_otm:.0f} call",
        "legs": [
            {"action": "Buy", "type": "put", "strike": put_otm, "premium": round(p_otm, 2), "lots": lots},
            {"action": "Sell", "type": "call", "strike": call_otm, "premium": round(c_otm, 2), "lots": lots},
        ],
        "net_cost": money(collar_net), "net_type": "debit" if collar_net > 0 else "credit",
        "cost_pct": pct(money(collar_net)),
        "floor": put_otm, "cap": call_otm,
        "protects": "Downside below the put strike, largely paid for by selling the upside.",
        "tradeoff": "Caps your gains above the call strike.",
    })

    # 5. Zero-cost collar — pick the call strike so the call premium ~ funds the put.
    zc_call = _zero_cost_call_strike(S, T, sigma, p_otm, step, atm)
    c_zc = bs_price("call", S, zc_call, T, sigma)
    zc_net = p_otm - c_zc
    strategies.append({
        "key": "zero_cost_collar",
        "name": "Zero-Cost Collar",
        "instrument": f"Buy {put_otm:.0f} put + Sell {zc_call:.0f} call",
        "legs": [
            {"action": "Buy", "type": "put", "strike": put_otm, "premium": round(p_otm, 2), "lots": lots},
            {"action": "Sell", "type": "call", "strike": zc_call, "premium": round(c_zc, 2), "lots": lots},
        ],
        "net_cost": money(zc_net), "net_type": "debit" if zc_net > 0 else "credit",
        "cost_pct": pct(money(zc_net)),
        "floor": put_otm, "cap": zc_call,
        "protects": "Downside below the put strike at little or no upfront cost.",
        "tradeoff": "Caps gains above the (higher) call strike chosen to fund the put.",
    })

    # 6. Bear put spread — buy ATM put, sell a lower put: cheap, capped protection.
    bps_net = p_atm - p_otm
    strategies.append({
        "key": "bear_put_spread",
        "name": "Bear Put Spread",
        "instrument": f"Buy {atm:.0f} put + Sell {put_otm:.0f} put",
        "legs": [
            {"action": "Buy", "type": "put", "strike": atm, "premium": round(p_atm, 2), "lots": lots},
            {"action": "Sell", "type": "put", "strike": put_otm, "premium": round(p_otm, 2), "lots": lots},
        ],
        "net_cost": money(bps_net), "net_type": "debit", "cost_pct": pct(money(bps_net)),
        "floor": atm, "cap": None,
        "protects": f"Cheap protection for a moderate fall (between {atm:.0f} and {put_otm:.0f}).",
        "tradeoff": f"Below {put_otm:.0f} you are unprotected again — only a partial hedge.",
    })

    # 7. Covered call — sell an OTM call for income / a small cushion.
    strategies.append({
        "key": "covered_call",
        "name": "Covered Call",
        "instrument": f"Sell {lots} lot(s) of {call_otm:.0f} call",
        "legs": [{"action": "Sell", "type": "call", "strike": call_otm, "premium": round(c_otm, 2), "lots": lots}],
        "net_cost": money(-c_otm), "net_type": "credit", "cost_pct": pct(money(-c_otm)),
        "floor": None, "cap": call_otm,
        "protects": "Premium received cushions a small drop and lowers your cost basis.",
        "tradeoff": "Not real downside protection in a crash, and it caps the upside above the strike.",
    })

    return {
        "lots": lots,
        "units": units,
        "beta_adjusted_exposure": round(exposure, 2),
        "strikes": {"atm": atm, "put_otm": put_otm, "call_otm": call_otm},
        "strategies": strategies,
    }
