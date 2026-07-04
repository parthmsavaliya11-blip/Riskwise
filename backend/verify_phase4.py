"""Phase 4 verification (ASCII-only prints).

Run from backend/:
    .venv\\Scripts\\Activate.ps1
    python verify_phase4.py

Checks risk analytics (concentration, correlation, VaR, drawdown, guardrail) and the
trade-journal stats against hand calculations, then exercises the live handlers.
"""

import numpy as np
import pandas as pd

from app.services.journal import r_multiple, summarize, trade_pnl
from app.services.risk import (
    concentration,
    correlation_matrix,
    daily_loss_guardrail,
    drawdown,
    value_at_risk,
)


def approx(a, b, tol):
    return a is not None and abs(a - b) <= tol


def check(label, ok):
    print(("PASS " if ok else "FAIL ") + label)
    return ok


print("== Concentration ==")
conc = concentration([
    {"symbol": "A", "value": 500000},
    {"symbol": "B", "value": 300000},
    {"symbol": "C", "value": 200000},
])
check("top1 = 50%", approx(conc["top1_pct"], 50.0, 0.01))
check("HHI = 0.5^2+0.3^2+0.2^2 = 0.38", approx(conc["hhi"], 0.38, 0.001))
check("single-stock + top3 flags raised", len(conc["flags"]) >= 2)

print("\n== Correlation ==")
base = np.random.default_rng(1).normal(0, 0.01, 200)
df = pd.DataFrame({"X": base, "Y": base * 1.0, "Z": -base})  # X,Y identical; Z opposite
cm = correlation_matrix(df)
check("X-Y correlation = 1.0", approx(dict((tuple(sorted((p["a"], p["b"]))), p["corr"]) for p in cm["high_pairs"]).get(("X", "Y")), 1.0, 0.001))
check("only X-Y flagged as high (>=0.7)", len(cm["high_pairs"]) == 1)

print("\n== Value at Risk ==")
rng = np.random.default_rng(2)
rets = rng.normal(0.0005, 0.012, 1000)
var = value_at_risk(rets, 1_000_000, 95)
expected_hist = max(-np.percentile(rets, 5), 0) * 1_000_000
check("historical VaR matches percentile", approx(var["historical_var"], round(expected_hist, 2), 1))
check("CVaR >= historical VaR (worse tail)", var["cvar"] >= var["historical_var"])
check("parametric VaR positive", var["parametric_var"] > 0)

print("\n== Drawdown ==")
eq = pd.Series([100.0, 120.0, 90.0, 110.0])
dd = drawdown(eq)
check("max drawdown = -25%", approx(dd["max_drawdown_pct"], -25.0, 0.01))
check("current drawdown = -8.33%", approx(dd["current_drawdown_pct"], -8.33, 0.02))

print("\n== Daily-loss guardrail ==")
check("loss 80% of cap -> approaching", daily_loss_guardrail(-8000, 10000)["status"] == "approaching")
check("loss over cap -> breached", daily_loss_guardrail(-12000, 10000)["status"] == "breached")
check("small loss -> ok", daily_loss_guardrail(-1000, 10000)["status"] == "ok")

print("\n== Journal math ==")
check("long R-multiple = 2.0", approx(r_multiple(100, 95, 110, "long"), 2.0, 0.001))
check("short R-multiple = 2.0", approx(r_multiple(100, 105, 90, "short"), 2.0, 0.001))
check("long P&L net of fees = 400", approx(trade_pnl(100, 110, 50, "long", 100), 400.0, 0.01))
stats = summarize([
    {"entry": 100, "stop": 95, "exit": 110, "quantity": 50, "side": "long", "fees": 0},
    {"entry": 100, "stop": 95, "exit": 95, "quantity": 50, "side": "long", "fees": 0},
    {"entry": 200, "stop": 190, "exit": 190, "quantity": 10, "side": "long", "fees": 0},
])
check("win rate = 33.33%", approx(stats["win_rate_pct"], 33.33, 0.1))
check("total P&L = 150", approx(stats["total_pnl"], 150.0, 0.01))
check("expectancy = 50/trade", approx(stats["expectancy_money"], 50.0, 0.01))
check("profit factor = 1.43", approx(stats["profit_factor"], 1.43, 0.01))
check("avg R = 0.0", approx(stats["avg_r"], 0.0, 0.001))

print("\n== Live handlers ==")
try:
    from app.api.risk import get_risk
    out = get_risk(confidence=95, daily_loss_limit=20000)
    check("risk: concentration flags present", len(out["concentration"]["flags"]) >= 1)
    check("risk: VaR available", out["var"]["available"] is True)
    check("risk: drawdown available", out["drawdown"]["available"] is True)
    check("risk: guardrail configured", out["guardrail"]["configured"] is True)
    check("risk: carries disclaimer", "disclaimer" in out)
    print("  1-day 95% VaR ~ {} ({}%)  max DD {}%  top sector {} {}%".format(
        out["var"]["historical_var"], out["var"]["historical_var_pct"],
        out["drawdown"]["max_drawdown_pct"],
        out["concentration"]["sectors"][0]["sector"], out["concentration"]["sectors"][0]["weight_pct"]))

    # Financial-year review: closed trades by exit-FY + still-open holdings held at year-end.
    from datetime import date
    from app.services.journal import review_financial_years
    rev = review_financial_years(
        [{"entry": 100, "stop": 95, "exit": 120, "quantity": 50, "side": "long", "fees": 0,
          "bucket": "F&O", "exit_date": "2025-08-01"}],
        [{"bucket": "Long-term", "invested": 100000, "unrealized_pnl": 25000, "buy_date": "2024-06-01"}],
        today=date(2026, 6, 28))
    fy26 = next(y for y in rev["financial_years"] if y["label"] == "FY2025-26")
    fy25 = next(y for y in rev["financial_years"] if y["label"] == "FY2024-25")
    check("journal: FY review groups closed trades by exit FY", fy26["overall"]["total_pnl"] == 1000.0)
    check("journal: FY review counts held positions at year-end",
          fy26["held_total"]["count"] == 1 and fy25["held_total"]["count"] == 1)
    check("journal: held position absent before its buy year",
          all(y["held_total"]["count"] == 0 for y in rev["financial_years"] if y["label"] < "FY2024-25"))
    check("journal: only completed FYs counted", rev["completed_count"] == 2)

    from app.db import SessionLocal, init_db
    from app.api.journal import create_trade, delete_trade, TradeIn
    init_db()
    db = SessionLocal()
    try:
        before = len(create_trade(TradeIn(symbol="TESTX", entry_price=100, stop_price=95,
                                          exit_price=110, quantity=50,
                                          entry_date="2025-07-01", exit_date="2025-08-01"), db)["trades"])
        res = create_trade(TradeIn(symbol="TESTY", entry_price=100, stop_price=95,
                                   exit_price=90, quantity=50,
                                   entry_date="2025-07-01", exit_date="2025-08-01"), db)
        check("journal: trades created + stats computed", res["stats"]["count"] >= 2)
        # clean up the test rows
        for t in [x for x in res["trades"] if x["symbol"] in ("TESTX", "TESTY")]:
            delete_trade(t["id"], db)
        check("journal: test rows cleaned up",
              all(x["symbol"] not in ("TESTX", "TESTY")
                  for x in __import__("app.api.journal", fromlist=["list_trades"]).list_trades(db)["trades"]))
    finally:
        db.close()
except Exception as e:
    import traceback
    print("  handler check failed:", type(e).__name__, e)
    traceback.print_exc()

print("\nDone.")
