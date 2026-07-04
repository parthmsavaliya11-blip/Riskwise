"""Options strategy engine — pure, auditable math.

Everything here is deterministic:
  * Black-Scholes pricing + Greeks (using math.erf for the normal CDF, so no scipy).
  * A theoretical option chain built from a spot price + implied vol, so the whole
    module is testable offline. In live mode the chain (strikes + premiums) is
    swapped in from the broker; payoff/Greeks math is unchanged.
  * A library of defined-leg strategies, each analysed for max profit, max loss,
    breakeven(s), net premium and net Greeks via a piecewise-linear payoff scan
    whose grid includes every strike (so the metrics are exact, not approximate).
  * A transparent ranking by fit to the user's view, conviction and budget.

The AI layer only narrates these numbers; it never invents them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

RISK_FREE = 0.065  # ~India 1y risk-free; only a small input to Greeks/pricing.

# Strike step + default lot size per index (exchange revises lots periodically).
INDEX_SPEC = {
    "NIFTY": {"step": 50, "lot_size": 50},
    "BANKNIFTY": {"step": 100, "lot_size": 15},
    "SENSEX": {"step": 100, "lot_size": 10},
}


# --------------------------------------------------------------------------- #
# Black-Scholes (no scipy: normal CDF via erf)
# --------------------------------------------------------------------------- #
def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def bs_price(kind: str, S: float, K: float, T: float, sigma: float, r: float = RISK_FREE) -> float:
    """Black-Scholes price of a European call/put."""
    if T <= 0 or sigma <= 0:
        # At/after expiry (or zero vol): worth its intrinsic value.
        return max(S - K, 0.0) if kind == "call" else max(K - S, 0.0)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if kind == "call":
        return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def bs_greeks(kind: str, S: float, K: float, T: float, sigma: float, r: float = RISK_FREE) -> dict:
    """Per-unit Greeks: delta, gamma, theta (per day), vega (per 1% vol)."""
    if T <= 0 or sigma <= 0:
        intrinsic_delta = (1.0 if S > K else 0.0) if kind == "call" else (-1.0 if S < K else 0.0)
        return {"delta": intrinsic_delta, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    sqrtT = math.sqrt(T)
    d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrtT)
    d2 = d1 - sigma * sqrtT
    pdf = _norm_pdf(d1)
    gamma = pdf / (S * sigma * sqrtT)
    vega = S * pdf * sqrtT  # per 1.0 change in sigma
    if kind == "call":
        delta = _norm_cdf(d1)
        theta = -(S * pdf * sigma) / (2 * sqrtT) - r * K * math.exp(-r * T) * _norm_cdf(d2)
    else:
        delta = _norm_cdf(d1) - 1.0
        theta = -(S * pdf * sigma) / (2 * sqrtT) + r * K * math.exp(-r * T) * _norm_cdf(-d2)
    return {
        "delta": delta,
        "gamma": gamma,
        "theta": theta / 365.0,   # per calendar day
        "vega": vega / 100.0,     # per 1% change in vol
    }


# --------------------------------------------------------------------------- #
# Chain + strategy model
# --------------------------------------------------------------------------- #
@dataclass
class Leg:
    kind: str        # "call" | "put"
    strike: float
    qty: int         # +1 long, -1 short (per lot)
    premium: float = 0.0


@dataclass
class Strategy:
    key: str
    name: str
    view: str        # bullish | bearish | neutral | volatile
    summary: str
    legs: list[Leg] = field(default_factory=list)


def atm_strike(spot: float, step: int) -> float:
    return round(spot / step) * step


def price_leg(leg: Leg, spot: float, T: float, sigma: float, r: float = RISK_FREE) -> Leg:
    leg.premium = round(bs_price(leg.kind, spot, leg.strike, T, sigma, r), 2)
    return leg


def build_strategies(spot: float, step: int, T: float, sigma: float, r: float = RISK_FREE) -> list[Strategy]:
    """The strategy library, with strikes chosen relative to ATM and premiums priced."""
    a = atm_strike(spot, step)
    s = step

    def C(strike, qty):
        return price_leg(Leg("call", strike, qty), spot, T, sigma, r)

    def P(strike, qty):
        return price_leg(Leg("put", strike, qty), spot, T, sigma, r)

    def U(qty):
        # The underlying itself, "bought" at spot — for covered call / protective put / collar.
        return Leg("underlying", round(spot, 2), qty, round(spot, 2))

    library: list[Strategy] = [
        Strategy("long_call", "Long Call", "bullish",
                 "Buy an ATM call. Defined cost, unlimited upside; loses if the market is flat or falls.",
                 [C(a, +1)]),
        Strategy("long_put", "Long Put", "bearish",
                 "Buy an ATM put. Defined cost, large downside profit; loses if the market is flat or rises.",
                 [P(a, +1)]),
        Strategy("bull_call_spread", "Bull Call Spread", "bullish",
                 "Buy ATM call, sell a higher call. Cheaper than a call, but caps the upside.",
                 [C(a, +1), C(a + 2 * s, -1)]),
        Strategy("bear_put_spread", "Bear Put Spread", "bearish",
                 "Buy ATM put, sell a lower put. Cheaper than a put, but caps the downside profit.",
                 [P(a, +1), P(a - 2 * s, -1)]),
        Strategy("bull_put_spread", "Bull Put Spread (credit)", "bullish",
                 "Sell ATM put, buy a lower put. Collect premium; profit if the market holds or rises.",
                 [P(a, -1), P(a - 2 * s, +1)]),
        Strategy("bear_call_spread", "Bear Call Spread (credit)", "bearish",
                 "Sell ATM call, buy a higher call. Collect premium; profit if the market holds or falls.",
                 [C(a, -1), C(a + 2 * s, +1)]),
        Strategy("iron_condor", "Iron Condor", "neutral",
                 "Sell a put spread and a call spread around the money. Profits if the market stays in a range.",
                 [P(a - 3 * s, +1), P(a - s, -1), C(a + s, -1), C(a + 3 * s, +1)]),
        Strategy("long_straddle", "Long Straddle", "volatile",
                 "Buy ATM call and put. Profits from a big move either way; loses if the market is quiet.",
                 [C(a, +1), P(a, +1)]),
        Strategy("long_strangle", "Long Strangle", "volatile",
                 "Buy OTM call and put. Cheaper than a straddle, but needs a bigger move to pay off.",
                 [C(a + 2 * s, +1), P(a - 2 * s, +1)]),

        # --- Neutral, defined-risk ---
        Strategy("long_call_butterfly", "Long Call Butterfly", "neutral",
                 "Buy 1 lower call, sell 2 ATM calls, buy 1 higher call. A cheap, defined-risk bet "
                 "that the market stays near today's level.",
                 [C(a - 2 * s, +1), C(a, -2), C(a + 2 * s, +1)]),
        Strategy("iron_butterfly", "Iron Butterfly", "neutral",
                 "Sell an ATM call and put, buy protective wings. A bigger credit than a condor if "
                 "the market sits still, but a narrower profit zone.",
                 [P(a - 2 * s, +1), P(a, -1), C(a, -1), C(a + 2 * s, +1)]),

        # --- Neutral, credit, UNDEFINED risk (premium selling) ---
        Strategy("short_straddle", "Short Straddle", "neutral",
                 "Sell an ATM call and put. Collects rich premium if the market barely moves — but "
                 "the loss is unlimited if it makes a big move.",
                 [C(a, -1), P(a, -1)]),
        Strategy("short_strangle", "Short Strangle", "neutral",
                 "Sell an OTM call and put. A wider safe zone than a short straddle for a smaller "
                 "credit; the loss is still unlimited.",
                 [C(a + 2 * s, -1), P(a - 2 * s, -1)]),
        Strategy("call_ratio_spread", "Call Ratio Spread", "neutral",
                 "Buy 1 ATM call, sell 2 higher calls. Cheap or free and profits on a mild rise — but "
                 "losses grow without limit if the market runs away upward.",
                 [C(a, +1), C(a + 2 * s, -2)]),

        # --- Hold-the-underlying overlays ---
        Strategy("covered_call", "Covered Call", "bullish",
                 "Hold the index and sell an OTM call for income. Caps your upside but lowers your "
                 "cost basis. Assumes you hold the underlying.",
                 [U(+1), C(a + 2 * s, -1)]),
        Strategy("protective_put", "Protective Put", "bullish",
                 "Hold the index and buy an ATM put as insurance. Keeps the full upside with a capped "
                 "downside. Assumes you hold the underlying.",
                 [U(+1), P(a, +1)]),
        Strategy("collar", "Collar", "bullish",
                 "Hold the index, buy a put and sell a call to fund it. Caps both downside and upside "
                 "for little or no cost. Assumes you hold the underlying.",
                 [U(+1), P(a - 2 * s, +1), C(a + 2 * s, -1)]),
    ]
    return library


# --------------------------------------------------------------------------- #
# Payoff analysis
# --------------------------------------------------------------------------- #
def _intrinsic(kind: str, S: float, K: float) -> float:
    if kind == "call":
        return max(S - K, 0.0)
    if kind == "put":
        return max(K - S, 0.0)
    return S  # "underlying": worth the spot price at expiry (held shares/index)


def payoff_at(legs: list[Leg], S: float) -> float:
    """Per-unit P&L at expiry for spot S (positive = profit)."""
    return sum(leg.qty * (_intrinsic(leg.kind, S, leg.strike) - leg.premium) for leg in legs)


def _breakevens(grid: list[float], pay: list[float]) -> list[float]:
    out: list[float] = []
    for i in range(1, len(grid)):
        y0, y1 = pay[i - 1], pay[i]
        if y0 == 0.0:
            out.append(grid[i - 1])
        elif y0 * y1 < 0:  # sign change -> linear interpolate the zero
            x0, x1 = grid[i - 1], grid[i]
            out.append(x0 + (x1 - x0) * (-y0) / (y1 - y0))
    # de-dup near-identical crossings
    uniq: list[float] = []
    for x in out:
        if not uniq or abs(x - uniq[-1]) > 1e-6:
            uniq.append(round(x, 2))
    return uniq


def analyze_strategy(strat: Strategy, spot: float, lot_size: int, T: float, sigma: float,
                     r: float = RISK_FREE) -> dict:
    """Full metrics for one strategy: net premium, max P/L, breakevens, Greeks, payoff curve."""
    legs = strat.legs
    net_premium_unit = sum(leg.qty * leg.premium for leg in legs)  # >0 = net debit (cost)

    # Analysis grid: dense + every option strike (kinks are at strikes, so metrics are
    # exact). The underlying leg is linear, so it needs no grid point. We include 0.01 so
    # the downside extreme (always bounded, since spot can't go below 0) is captured.
    strikes = sorted({leg.strike for leg in legs if leg.kind != "underlying"})
    lo, hi = max(0.01, spot * 0.5), spot * 1.5
    n = 301
    grid = sorted(set([lo + (hi - lo) * i / (n - 1) for i in range(n)]) | set(strikes) | {0.01})
    pay_unit = [payoff_at(legs, S) for S in grid]

    # Behaviour as spot -> infinity is set by the net call + underlying position (puts go
    # to zero). >0 => unlimited PROFIT on the upside; <0 => unlimited LOSS (naked/ratio
    # short calls). The downside (spot -> 0) is always bounded.
    upside_slope = sum(leg.qty for leg in legs if leg.kind in ("call", "underlying"))
    unbounded_profit = upside_slope > 0
    unbounded_loss = upside_slope < 0
    max_profit_unit = None if unbounded_profit else max(pay_unit)
    max_loss_unit = None if unbounded_loss else min(pay_unit)

    breakevens = _breakevens(grid, pay_unit)

    # Greeks at current spot, summed across legs (per lot). The underlying has delta 1 and
    # no gamma/theta/vega.
    g = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    for leg in legs:
        if leg.kind == "underlying":
            lg = {"delta": 1.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
        else:
            lg = bs_greeks(leg.kind, spot, leg.strike, T, sigma, r)
        for k in g:
            g[k] += leg.qty * lg[k] * lot_size

    max_loss = None if max_loss_unit is None else max_loss_unit * lot_size
    max_profit = None if max_profit_unit is None else max_profit_unit * lot_size
    capital_required = abs(max_loss) if max_loss is not None else None  # None => margin/undefined
    reward_risk = (max_profit / capital_required) if (max_profit and capital_required) else None

    # Chart curve (lighter grid around spot for a smooth line).
    cn = 81
    clo, chi = spot * 0.7, spot * 1.3
    curve = [
        {"spot": round(clo + (chi - clo) * i / (cn - 1), 2),
         "pnl": round(payoff_at(legs, clo + (chi - clo) * i / (cn - 1)) * lot_size, 2)}
        for i in range(cn)
    ]

    return {
        "key": strat.key,
        "name": strat.name,
        "view": strat.view,
        "summary": strat.summary,
        "legs": [
            {"action": "Buy" if leg.qty > 0 else "Sell", "kind": leg.kind,
             "strike": leg.strike, "qty": abs(leg.qty), "premium": leg.premium}
            for leg in legs
        ],
        "net_premium": round(net_premium_unit * lot_size, 2),
        "net_type": "debit" if net_premium_unit > 0 else "credit",
        "max_profit": None if max_profit is None else round(max_profit, 2),
        "max_profit_unbounded": unbounded_profit,
        "max_loss": None if max_loss is None else round(max_loss, 2),
        "max_loss_unbounded": unbounded_loss,
        "capital_required": None if capital_required is None else round(capital_required, 2),
        "reward_risk": None if reward_risk is None else round(reward_risk, 2),
        "breakevens": breakevens,
        "greeks": {k: round(v, 4) for k, v in g.items()},
        "payoff_curve": curve,
    }


# --------------------------------------------------------------------------- #
# Basket analysis (user-built legs: futures + options, live premiums)
# --------------------------------------------------------------------------- #
def implied_vol(kind: str, S: float, K: float, T: float, price: float,
                r: float = RISK_FREE) -> float:
    """Back out implied vol from a live option premium (bisection). 0 if not solvable."""
    if T <= 0 or price <= 0:
        return 0.0
    intrinsic = max(S - K, 0.0) if kind == "call" else max(K - S, 0.0)
    if price <= intrinsic + 1e-6:
        return 0.0  # all intrinsic, no time value -> vol is undefined
    lo, hi = 0.005, 4.0
    for _ in range(64):
        mid = 0.5 * (lo + hi)
        if bs_price(kind, S, K, T, mid, r) > price:
            hi = mid
        else:
            lo = mid
    return round(0.5 * (lo + hi), 4)


def enrich_chain_greeks(chain: dict, r: float = RISK_FREE) -> dict:
    """Add implied vol + Greeks to each strike of a live option chain (in place).

    OI and premium are raw market data (fetched by the feed); the Greeks are *derived*,
    so — per the math-vs-data separation — they're computed here from the deterministic
    Black-Scholes engine: back out each option's implied vol from its live premium, then
    price delta/gamma/theta/vega off that vol. Spot is the chain's forward (``ref_price``)
    and T comes from ``days_to_expiry``. A side with no usable premium gets null Greeks.
    """
    spot = float(chain.get("ref_price") or 0)
    T = max(int(chain.get("days_to_expiry") or 0), 0) / 365.0

    def _greeks(kind: str, strike: float, ltp: float) -> dict:
        if spot <= 0 or T <= 0 or not ltp or ltp <= 0 or not strike:
            return {"iv": None, "delta": None, "gamma": None, "theta": None, "vega": None}
        iv = implied_vol(kind, spot, float(strike), T, float(ltp), r)
        if iv <= 0:
            return {"iv": None, "delta": None, "gamma": None, "theta": None, "vega": None}
        g = bs_greeks(kind, spot, float(strike), T, iv, r)
        return {
            "iv": round(iv * 100, 1),          # percent
            "delta": round(g["delta"], 3),
            "gamma": round(g["gamma"], 5),
            "theta": round(g["theta"], 2),     # premium lost per calendar day
            "vega": round(g["vega"], 2),       # premium gained per 1% vol
        }

    for row in chain.get("rows", []):
        if row.get("ce"):
            row["ce"].update(_greeks("call", row["strike"], row["ce"].get("ltp")))
        if row.get("pe"):
            row["pe"].update(_greeks("put", row["strike"], row["pe"].get("ltp")))
    return chain


def analyze_basket(legs: list[Leg], spot: float, lot_size: int, T: float,
                   default_sigma: float = 0.18, r: float = RISK_FREE) -> dict:
    """Full payoff/risk for a user-built basket of legs (futures + options).

    Payoff, max P/L and breakevens are EXACT (from the entered/live premiums).
    Greeks use each option's own implied vol (backed out from its premium). A
    futures leg is modelled as an ``underlying`` leg priced at its entry — it has
    no upfront premium, so it's excluded from the net option debit/credit.
    """
    option_legs = [l for l in legs if l.kind in ("call", "put")]
    net_premium_unit = sum(l.qty * l.premium for l in option_legs)  # >0 = net debit

    strikes = sorted({l.strike for l in legs if l.kind != "underlying"})
    lo, hi = max(0.01, spot * 0.5), spot * 1.5
    n = 301
    grid = sorted(set([lo + (hi - lo) * i / (n - 1) for i in range(n)]) | set(strikes) | {0.01})
    pay_unit = [payoff_at(legs, S) for S in grid]

    upside_slope = sum(l.qty for l in legs if l.kind in ("call", "underlying"))
    unbounded_profit = upside_slope > 0
    unbounded_loss = upside_slope < 0
    max_profit_unit = None if unbounded_profit else max(pay_unit)
    max_loss_unit = None if unbounded_loss else min(pay_unit)
    breakevens = _breakevens(grid, pay_unit)

    g = {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    legs_out = []
    for l in legs:
        if l.kind == "underlying":
            lg, iv = {"delta": 1.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}, None
        else:
            iv = implied_vol(l.kind, spot, l.strike, T, l.premium, r) or default_sigma
            lg = bs_greeks(l.kind, spot, l.strike, T, iv, r)
        for k in g:
            g[k] += l.qty * lg[k] * lot_size
        legs_out.append({
            "action": "Buy" if l.qty > 0 else "Sell",
            # "underlying" here is a futures leg in the basket UI — label it so for clarity.
            "kind": "future" if l.kind == "underlying" else l.kind,
            "strike": None if l.kind == "underlying" else l.strike, "lots": abs(l.qty),
            "premium": l.premium, "iv_pct": None if iv is None else round(iv * 100, 1),
        })

    max_loss = None if max_loss_unit is None else round(max_loss_unit * lot_size, 2)
    max_profit = None if max_profit_unit is None else round(max_profit_unit * lot_size, 2)
    net_premium = round(net_premium_unit * lot_size, 2)

    cn = 81
    clo, chi = spot * 0.7, spot * 1.3
    curve = [
        {"spot": round(clo + (chi - clo) * i / (cn - 1), 2),
         "pnl": round(payoff_at(legs, clo + (chi - clo) * i / (cn - 1)) * lot_size, 2)}
        for i in range(cn)
    ]

    # Inferred directional bias from net delta, expressed in net lots of exposure.
    net_lots = g["delta"] / lot_size if lot_size else 0.0
    if abs(net_lots) < 0.15:
        view = "volatile" if (g["vega"] > 0 and g["gamma"] > 0) else "neutral"
    else:
        view = "bullish" if net_lots > 0 else "bearish"

    # Rule-based, plain-language observations (computed, not AI).
    obs: list[str] = []
    obs.append(
        f"Net position leans {view}" + (
            "" if view in ("neutral", "volatile") else f" (~{abs(round(net_lots, 2))} lots of delta)"))
    if net_premium > 0:
        obs.append(f"Net debit of Rs {net_premium:,.0f} - you pay this upfront (options).")
    elif net_premium < 0:
        obs.append(f"Net credit of Rs {abs(net_premium):,.0f} - you receive this upfront (options).")
    obs.append("Max loss is UNLIMITED" if unbounded_loss
               else f"Max loss is capped at Rs {abs(max_loss):,.0f}.")
    obs.append("Max profit is UNLIMITED" if unbounded_profit
               else f"Max profit is capped at Rs {max_profit:,.0f}.")
    if g["theta"] < 0:
        obs.append(f"Time decay works against you (~Rs {abs(round(g['theta'],0)):,.0f}/day).")
    elif g["theta"] > 0:
        obs.append(f"Time decay works for you (~Rs {round(g['theta'],0):,.0f}/day).")

    return {
        "legs": legs_out,
        "lot_size": lot_size,
        "spot": round(spot, 2),
        "net_premium": net_premium,
        "net_type": "debit" if net_premium_unit > 0 else "credit",
        "max_profit": max_profit,
        "max_profit_unbounded": unbounded_profit,
        "max_loss": max_loss,
        "max_loss_unbounded": unbounded_loss,
        "breakevens": breakevens,
        "greeks": {k: round(v, 2) for k, v in g.items()},
        "view": view,
        "observations": obs,
        "payoff_curve": curve,
    }


# --------------------------------------------------------------------------- #
# Ranking by fit to the user's view / conviction / budget
# --------------------------------------------------------------------------- #
def _score(metrics: dict, view: str, conviction: str, budget: float | None) -> float:
    """Transparent fit score. View match dominates; then reward:risk, budget, conviction."""
    score = 0.0
    if metrics["view"] == view:
        score += 100.0
    rr = metrics["reward_risk"]
    if rr is not None:
        score += min(rr, 5.0) * 8.0
    elif metrics["max_profit_unbounded"]:
        score += 30.0  # unlimited upside is attractive for strong directional views
    # Unlimited-loss structures (short straddle/strangle, ratio spreads) are demoted so
    # defined-risk strategies surface first for the same view.
    if metrics.get("max_loss_unbounded"):
        score -= 25.0
    cap = metrics["capital_required"]
    if budget and cap is not None:
        score += 20.0 if cap <= budget else -60.0
    # Conviction: high -> favour directional long delta; low -> favour cheaper/credit.
    delta_mag = abs(metrics["greeks"]["delta"])
    if conviction == "high":
        score += min(delta_mag / 50.0, 1.0) * 15.0
    elif conviction == "low":
        if metrics["net_type"] == "credit":
            score += 12.0
        if cap is not None:
            score += max(0.0, 10.0 - cap / 5000.0)
    return round(score, 2)


def recommend(spot: float, sigma: float, T: float, lot_size: int, step: int,
              view: str, conviction: str = "medium", budget: float | None = None,
              r: float = RISK_FREE) -> dict:
    """Rank the library for the user's view; return all candidates with the best flagged."""
    strategies = build_strategies(spot, step, T, sigma, r)
    analysed = [analyze_strategy(s, spot, lot_size, T, sigma, r) for s in strategies]

    matching = [m for m in analysed if m["view"] == view] or analysed
    for m in matching:
        m["fit_score"] = _score(m, view, conviction, budget)
        cap = m["capital_required"]
        m["affordable"] = (budget is None) or (cap is not None and cap <= budget)
    matching.sort(key=lambda m: m["fit_score"], reverse=True)
    if matching:
        matching[0]["recommended"] = True
    return {"candidates": matching}
