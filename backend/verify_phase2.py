"""Phase 2 math verification (ASCII-only prints; Windows cp1252 safe).

Run from backend/:
    .venv\\Scripts\\Activate.ps1
    python generate_sample_history.py   # if data/history is missing
    python verify_phase2.py

Checks the beta engine recovers known betas, the hedge sizing matches a hand
calc, and the live /api/hedge handler runs end-to-end on the sample portfolio.
"""

import numpy as np

from app.services.hedge import (
    build_hedge_strategies,
    compute_beta,
    hedge_with_futures,
    hedge_with_puts,
    portfolio_beta,
)


def approx(a, b, tol):
    return a is not None and abs(a - b) <= tol


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label)
    return ok


print("== Beta engine (synthetic) ==")
rng = np.random.default_rng(7)
idx = rng.normal(0.0003, 0.01, 500)
# Exact beta 1.3, no noise -> beta 1.3, R^2 = 1.
res = compute_beta(1.3 * idx, idx)
check("beta recovered = 1.30", approx(res["beta"], 1.30, 0.001))
check("R^2 = 1.0 (perfect fit)", approx(res["r_squared"], 1.0, 0.001))
# With noise -> beta still ~0.8, R^2 < 1.
noisy = 0.8 * idx + rng.normal(0, 0.008, 500)
res2 = compute_beta(noisy, idx)
check("noisy beta ~ 0.8", approx(res2["beta"], 0.8, 0.08))
check("noisy R^2 in (0,1)", 0.0 < res2["r_squared"] < 1.0)
check("too little data -> None", compute_beta([0.01], [0.02]) is None)

print("\n== Portfolio beta ==")
pb = portfolio_beta(
    [
        {"symbol": "A", "value": 600000, "beta": 1.0},
        {"symbol": "B", "value": 400000, "beta": 0.5},
    ]
)
# 0.6*1.0 + 0.4*0.5 = 0.8
check("weighted beta = 0.80", approx(pb["portfolio_beta"], 0.80, 0.001))
check("total value = 1,000,000", approx(pb["total_value"], 1_000_000, 0.01))

print("\n== Hedge sizing (hand calc) ==")
f = hedge_with_futures(1_000_000, 1.2, 23600, 50)
# exposure 1,200,000 / contract 1,180,000 = 1.017 -> 1 lot; residual 20,000.
check("lots_to_short = 1", f["lots_to_short"] == 1)
check("beta-adjusted exposure = 1,200,000", approx(f["beta_adjusted_exposure"], 1_200_000, 1))
check("residual exposure = 20,000", approx(f["residual_exposure"], 20_000, 1))
p = hedge_with_puts(1_000_000, 1.2, 23600, 50, 236)
# 1 lot of 50 * 236 premium = 11,800
check("put cost = 11,800", approx(p["est_cost"], 11_800, 1))

print("\n== Hedging-strategy library ==")
lib = build_hedge_strategies(1_500_000, 1.0, 23500, 50, 0.14, 30 / 365, 50)
by_key = {s["key"]: s for s in lib["strategies"]}
check("seven strategies returned", len(lib["strategies"]) == 7)
check("short futures has zero upfront cost (margin)",
      by_key["short_futures"]["net_cost"] == 0.0 and by_key["short_futures"]["net_type"] == "margin")
check("ATM put costs more than OTM put",
      by_key["protective_put_atm"]["net_cost"] > by_key["protective_put_otm"]["net_cost"] > 0)
check("bear put spread is cheaper than the outright ATM put",
      0 < by_key["bear_put_spread"]["net_cost"] < by_key["protective_put_atm"]["net_cost"])
check("collar is cheaper than the OTM put alone (call funds it)",
      by_key["collar"]["net_cost"] < by_key["protective_put_otm"]["net_cost"])
check("covered call is a credit (you receive premium)",
      by_key["covered_call"]["net_type"] == "credit" and by_key["covered_call"]["net_cost"] < 0)
check("zero-cost collar is ~free (|net| < OTM put cost)",
      abs(by_key["zero_cost_collar"]["net_cost"]) < by_key["protective_put_otm"]["net_cost"])
check("collar has both a floor and a cap",
      by_key["collar"]["floor"] is not None and by_key["collar"]["cap"] is not None)

print("\n== Live /api/hedge handler ==")
try:
    from app.api.hedge import get_hedge

    out = get_hedge(index="NIFTY", index_price=23615, lot_size=50)
    if "error" in out:
        print("  handler returned error:", out["error"])
    else:
        by = {r["symbol"]: r for r in out["rows"]}
        src = out["data_quality"]["history_source"]
        print("  history source:", src)

        # Offline with the sample portfolio loaded: betas should recover known targets.
        sample_targets = {
            "RELIANCE": 1.05, "HDFCBANK": 1.15, "TCS": 0.75, "TATAMOTORS": 1.55,
            "ICICIBANK": 1.20, "INFY": 0.80, "NIFTY24JUNFUT": 1.00,
        }
        present = [s for s in sample_targets
                   if s in by and by[s]["beta"] is not None]
        if src == "csv" and len(present) >= 4:
            all_ok = True
            for sym in present:
                got = by[sym]["beta"]
                ok = approx(got, sample_targets[sym], 0.15)  # ~2 SE on ~1yr daily
                all_ok = all_ok and ok
                print("  {:>14}  beta {:>5}  (target {:>4})  {}".format(
                    sym, got, sample_targets[sym], "ok" if ok else "OFF"))
            check("sample betas within noise of target", all_ok)
        else:
            print("  (live/real portfolio: checking index-differentiation instead)")

        # The Phase-2 bug fix: choosing a different index must move the portfolio beta.
        # Previously every holding without sample history fell back to beta 1.0, so all
        # indices reported ~1.00. With real per-index regressions they must differ.
        betas = {}
        for idx in ("NIFTY", "BANKNIFTY", "SENSEX"):
            o = get_hedge(index=idx)
            if "error" not in o:
                betas[idx] = o["portfolio_beta"]
        print("  portfolio betas by index:", betas)
        has_real = any(r["has_history"] for r in out["rows"])
        distinct = len({round(b, 2) for b in betas.values()})
        check("portfolio beta differs across indices when betas are real",
              distinct > 1 or not has_real)

        check("portfolio beta reported", out["portfolio_beta"] is not None)
        check("hedge lots is an int", isinstance(out["hedge_futures"]["lots_to_short"], int))
        check("response carries disclaimer", "disclaimer" in out)
        print("  portfolio value {}  beta {}  -> short {} lot(s) of NIFTY".format(
            out["portfolio_value"], out["portfolio_beta"],
            out["hedge_futures"]["lots_to_short"]))
except Exception as e:
    import traceback
    print("  handler check failed:", type(e).__name__, e)
    traceback.print_exc()

print("\nDone.")
