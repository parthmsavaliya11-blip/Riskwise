"""Phase 3 options-engine verification (ASCII-only prints).

Run from backend/:
    .venv\\Scripts\\Activate.ps1
    python verify_phase3.py

Checks Black-Scholes (put-call parity), and that the payoff engine reproduces the
textbook max-profit / max-loss / breakeven formulas for representative strategies,
plus Greek signs and the ranking.
"""

import math

from app.services.options import (
    INDEX_SPEC,
    analyze_strategy,
    atm_strike,
    bs_price,
    build_strategies,
    recommend,
)

SPOT, STEP, LOT = 23500.0, 50, 50
IV, T, R = 0.14, 30 / 365, 0.065


def approx(a, b, tol):
    return a is not None and abs(a - b) <= tol


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label)
    return ok


print("== Black-Scholes ==")
K = 23500.0
c = bs_price("call", SPOT, K, T, IV, R)
p = bs_price("put", SPOT, K, T, IV, R)
# Put-call parity: C - P = S - K e^{-rT}
parity = (c - p) - (SPOT - K * math.exp(-R * T))
check("call & put both positive", c > 0 and p > 0)
check("put-call parity holds", approx(parity, 0.0, 0.5))

strategies = {s.key: s for s in build_strategies(SPOT, STEP, T, IV, R)}


def M(key):
    return analyze_strategy(strategies[key], SPOT, LOT, T, IV, R)


print("\n== Long Call ==")
lc = M("long_call")
prem_unit = lc["net_premium"] / LOT
check("max loss = -premium*lot", approx(lc["max_loss"], -lc["net_premium"], 1))
check("profit is unbounded", lc["max_profit_unbounded"] is True)
check("breakeven = strike + premium", approx(lc["breakevens"][0], 23500 + prem_unit, 2))
check("delta in (0,1) per unit", 0 < lc["greeks"]["delta"] / LOT < 1)

print("\n== Bull Call Spread ==")
bcs = M("bull_call_spread")
debit_unit = bcs["net_premium"] / LOT
# width = 2*step = 100; max profit = (100 - debit)*lot ; max loss = -debit*lot
check("net is a debit", bcs["net_type"] == "debit")
check("max profit = (width - debit)*lot", approx(bcs["max_profit"], (2 * STEP - debit_unit) * LOT, 2))
check("max loss = -debit*lot", approx(bcs["max_loss"], -bcs["net_premium"], 2))
check("breakeven = lowK + debit", approx(bcs["breakevens"][0], 23500 + debit_unit, 2))

print("\n== Iron Condor ==")
ic = M("iron_condor")
credit_unit = -ic["net_premium"] / LOT  # net_premium negative for a credit
check("net is a credit", ic["net_type"] == "credit")
check("max profit = credit*lot", approx(ic["max_profit"], credit_unit * LOT, 2))
# wing width 2*step; max loss = -(width - credit)*lot
check("max loss = -(width - credit)*lot", approx(ic["max_loss"], -((2 * STEP) - credit_unit) * LOT, 2))
check("two breakevens", len(ic["breakevens"]) == 2)

print("\n== Long Straddle ==")
ls = M("long_straddle")
cost_unit = ls["net_premium"] / LOT
check("max loss = -cost*lot", approx(ls["max_loss"], -ls["net_premium"], 2))
check("profit unbounded", ls["max_profit_unbounded"] is True)
check("breakevens ~ K +/- cost", approx(ls["breakevens"][0], 23500 - cost_unit, 2)
      and approx(ls["breakevens"][-1], 23500 + cost_unit, 2))
check("vega positive (long vol)", ls["greeks"]["vega"] > 0)
check("theta negative (time decay)", ls["greeks"]["theta"] < 0)

print("\n== New strategies ==")
lcb = M("long_call_butterfly")
# Defined risk both ways; max profit at the centre strike (a); cost is a small debit.
check("call butterfly: bounded profit & loss",
      lcb["max_profit"] is not None and lcb["max_loss"] is not None)
check("call butterfly: small net debit", lcb["net_type"] == "debit" and lcb["max_loss"] < 0)
ss = M("short_straddle")
check("short straddle: UNLIMITED loss flagged", ss["max_loss_unbounded"] is True and ss["max_loss"] is None)
check("short straddle: credit + bounded profit", ss["net_type"] == "credit" and ss["max_profit"] is not None)
crs = M("call_ratio_spread")
check("call ratio spread: unlimited loss (net short calls)", crs["max_loss_unbounded"] is True)
ib = M("iron_butterfly")
check("iron butterfly: credit, defined risk",
      ib["net_type"] == "credit" and ib["max_loss"] is not None and ib["max_profit"] is not None)
cc = M("covered_call")
# Long underlying + short call: bounded both ways, delta ~ +1 lot (50) minus the short call delta.
check("covered call: bounded (capped upside)",
      cc["max_profit"] is not None and not cc["max_loss_unbounded"])
check("covered call: net long delta", cc["greeks"]["delta"] > 0)
pp = M("protective_put")
check("protective put: unlimited upside (hold stock)", pp["max_profit_unbounded"] is True)
check("protective put: downside is capped (defined max loss)", pp["max_loss"] is not None)
col = M("collar")
check("collar: bounded both sides", col["max_profit"] is not None and col["max_loss"] is not None)
check("library now has 17 strategies", len(strategies) == 17)

print("\n== Ranking ==")
bull = recommend(SPOT, IV, T, LOT, STEP, view="bullish", conviction="high", budget=50000)
top_bull = bull["candidates"][0]
check("bullish view -> bullish top pick", top_bull["view"] == "bullish")
check("top pick flagged recommended", top_bull.get("recommended") is True)
neutral = recommend(SPOT, IV, T, LOT, STEP, view="neutral", conviction="medium", budget=50000)
check("neutral view -> iron condor top", neutral["candidates"][0]["key"] == "iron_condor")
vol = recommend(SPOT, IV, T, LOT, STEP, view="volatile", conviction="high", budget=200000)
check("volatile view -> straddle/strangle top", vol["candidates"][0]["key"] in ("long_straddle", "long_strangle"))

print("\n== Live /api/options handler ==")
try:
    from app.api.options import get_options
    out = get_options(index="NIFTY", view="bullish", conviction="high", budget=50000, days_to_expiry=30)
    check("handler returns candidates", len(out["candidates"]) >= 1)
    check("carries disclaimer", "disclaimer" in out)
    rec = next((c for c in out["candidates"] if c.get("recommended")), out["candidates"][0])
    print("  spot {}  IV {}%  -> recommended: {} (max loss {}, max profit {})".format(
        out["spot"], out["iv_pct"], rec["name"], rec["max_loss"],
        "unlimited" if rec["max_profit_unbounded"] else rec["max_profit"]))
except Exception as e:
    print("  handler check failed:", type(e).__name__, e)

print("\nDone.")
