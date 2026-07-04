"""Phase 1 math verification (ASCII-only prints; Windows cp1252 safe).

Run from backend/ with backend/ on PYTHONPATH:
    .venv\\Scripts\\Activate.ps1
    python verify_phase1.py

Checks the pure services against hand calculations + exercises the live API
handlers (allocation + buckets) against the sample CSV portfolio.
"""

from datetime import date

from app.services.allocation import BucketActual, BucketTarget, analyze_allocation
from app.services.sizing import SizingInput, size_position
from app.services.xirr import xirr


def approx(a, b, tol=0.01):
    return abs(a - b) <= tol


def check(label, condition):
    print(("PASS " if condition else "FAIL ") + label)
    return condition


print("== Allocation ==")
targets = [
    BucketTarget("F&O", 20, 5),
    BucketTarget("Long-term", 30, 5),
    BucketTarget("Swing", 50, 5),
]
actuals = [
    BucketActual("F&O", 200000, 180000),
    BucketActual("Long-term", 300000, 250000),
    BucketActual("Swing", 500000, 520000),
]
rep = analyze_allocation(targets, actuals)
# Total 1,000,000 -> F&O 20%, Long 30%, Swing 50% -> all exactly on target.
by = {r["bucket"]: r for r in rep["rows"]}
check("total value = 1,000,000", approx(rep["total_value"], 1_000_000))
check("F&O current% = 20", approx(by["F&O"]["current_pct"], 20))
check("F&O in-band (drift 0)", by["F&O"]["status"] == "in-band")
check("targets sum to 100 -> valid", rep["targets_valid"] is True)

# Now skew it: move Swing up so it breaches the +5% band.
actuals2 = [
    BucketActual("F&O", 100000, 100000),
    BucketActual("Long-term", 300000, 250000),
    BucketActual("Swing", 600000, 520000),
]
rep2 = analyze_allocation(targets, actuals2)
by2 = {r["bucket"]: r for r in rep2["rows"]}
# Total 1,000,000 -> Swing 60% vs target 50 -> drift +10 -> over band.
check("Swing 60% -> over band", by2["Swing"]["status"] == "over")
check("Swing rebalance = -100,000 (trim)", approx(by2["Swing"]["rebalance_value"], -100000))
check("F&O 10% -> under band", by2["F&O"]["status"] == "under")
check("any_drifted flag set", rep2["any_drifted"] is True)

print("\n== Position sizing ==")
res = size_position(
    SizingInput(account_size=1_000_000, risk_per_trade_pct=1, entry_price=100, stop_price=95)
)
check("qty = 2000 (10,000 budget / 5 risk)", res["quantity"] == 2000)
check("actual risk = 10,000", approx(res["actual_risk"], 10000))
check("risk% of account = 1.0", approx(res["risk_pct_of_account"], 1.0))
check("position value = 200,000", approx(res["position_value"], 200000))

# F&O lot rounding: lot size 50.
res2 = size_position(
    SizingInput(
        account_size=500_000, risk_per_trade_pct=2, entry_price=23600,
        stop_price=23400, lot_size=50,
    )
)
# budget 10,000 / 200 per-unit = 50 units -> 1 lot of 50.
check("F&O rounds to 1 lot (qty 50)", res2["quantity"] == 50 and res2["lots"] == 1)

bad = size_position(
    SizingInput(account_size=100000, risk_per_trade_pct=1, entry_price=100, stop_price=100)
)
check("zero stop distance -> error", bad["ok"] is False)

print("\n== XIRR ==")
r = xirr([(date(2024, 1, 1), -100000), (date(2025, 1, 1), 110000)])
check("one-year +10% -> ~0.10", r is not None and approx(r, 0.10, 0.002))
r2 = xirr([(date(2024, 1, 1), 100), (date(2025, 1, 1), 100)])
check("all same sign -> None", r2 is None)

print("\n== Live API handlers (sample CSV portfolio) ==")
try:
    from app.db import SessionLocal, init_db
    from app.api.buckets import seed_default_buckets, list_buckets
    from app.api.allocation import get_allocation

    init_db()
    seed_default_buckets()
    db = SessionLocal()
    try:
        b = list_buckets(db)
        check("buckets seeded (3 default)", len(b["buckets"]) == 3)
        alloc = get_allocation(db)
        check("allocation has rows", len(alloc["rows"]) >= 1)
        check("allocation carries disclaimer", "disclaimer" in alloc)
        print("  total portfolio value:", alloc["total_value"])
        for row in alloc["rows"]:
            print(
                "  {:>10}  cur {:>6}%  target {:>5}%  {}".format(
                    row["bucket"], row["current_pct"], row["target_pct"], row["status"]
                )
            )
    finally:
        db.close()
except Exception as e:
    print("API handler check skipped/failed:", type(e).__name__, e)

print("\nDone.")
