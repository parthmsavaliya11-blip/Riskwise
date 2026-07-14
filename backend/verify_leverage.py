"""Verify the F&O leverage-aware (Angel-margin-as-capital) math. Offline / pure."""
from app.data.provider import Holding
from app.holdings import resolve_fno_margins


def approx(a, b, tol=0.05):
    return abs(a - b) <= tol


def test_equity_unchanged():
    h = Holding(symbol="TCS", quantity=10, avg_price=3000, ltp=3200, kind="EQ")
    assert h.margin is None
    assert approx(h.capital, 30000)            # cost basis
    assert approx(h.capital_value, 32000)      # market value = qty*ltp
    assert approx(h.pnl, 2000)
    assert approx(h.capital_pnl_pct, 2000 / 30000 * 100)
    assert h.leverage is None
    print("OK equity: capital=cost, value=market, no leverage")


def test_long_future_leverage():
    h = Holding(symbol="NIFTY", quantity=50, avg_price=24000, ltp=24200,
                kind="FUT", side="buy", margin=120000)
    assert approx(h.invested, 1_200_000)       # notional cost (hedge/risk still see this)
    assert approx(h.current_value, 1_210_000)  # notional value
    assert approx(h.pnl, 10_000)               # rupee P&L exact
    assert approx(h.capital, 120_000)          # capital = Angel margin
    assert approx(h.capital_value, 130_000)    # margin + MTM
    assert approx(h.capital_pnl_pct, 10_000 / 120_000 * 100)  # ~8.33% leveraged return
    assert approx(h.leverage, 10.08, tol=0.02)
    print(f"OK long future: capital={h.capital:.0f} lev={h.leverage:.2f} ret={h.capital_pnl_pct:.2f}%")


def test_short_future_signs():
    h = Holding(symbol="NIFTY", quantity=50, avg_price=24000, ltp=24200,
                kind="FUT", side="sell", margin=120000)
    assert approx(h.pnl, -10_000)              # short loses when price rises
    assert approx(h.capital, 120_000)
    assert approx(h.capital_value, 110_000)    # margin minus the loss
    assert approx(h.capital_pnl_pct, -10_000 / 120_000 * 100)
    print("OK short future: P&L sign correct, capital=margin")


def test_margin_fallback_to_notional():
    # No margin resolved (feed off) -> capital view collapses to notional cost/value.
    h = Holding(symbol="NIFTY", quantity=50, avg_price=24000, ltp=24200, kind="FUT")
    assert approx(h.capital, 1_200_000)
    assert approx(h.capital_value, 1_210_000)
    assert h.leverage is None
    print("OK fallback: no margin -> notional (offline safe)")


class FakeMkt:
    """Stub feed: 'margin' = 10% of the netted notional of the leg-set."""
    def __init__(self):
        self.calls = 0

    def basket_margin_total(self, pos):
        self.calls += 1
        return round(sum(abs(p["qty"]) * p["price"] for p in pos) * 0.10, 2)


def test_resolve_grouping_and_split():
    mkt = FakeMkt()
    legs = [
        # standalone future
        {"key": 1, "token": "t1", "exchange": "NFO", "qty": 50, "price": 24200,
         "side": "buy", "kind": "FUT", "basket_id": None},
        # a saved basket: short future + long put (netted into ONE margin call)
        {"key": 2, "token": "t2", "exchange": "NFO", "qty": 50, "price": 24200,
         "side": "sell", "kind": "FUT", "basket_id": "b1"},
        {"key": 3, "token": "t3", "exchange": "NFO", "qty": 50, "price": 100,
         "side": "buy", "kind": "PE", "basket_id": "b1"},
        # equity -> no margin
        {"key": 4, "token": "t4", "exchange": "NSE", "qty": 10, "price": 3200,
         "side": "buy", "kind": "EQ", "basket_id": None},
    ]
    out = resolve_fno_margins(legs, mkt)
    assert 4 not in out, "equity must not get a margin"
    assert 1 in out and 2 in out and 3 in out
    # standalone future: one call, 10% of its notional
    assert approx(out[1], 50 * 24200 * 0.10, tol=1.0)
    # basket b1 netted: total split across its two legs sums to the group margin
    group_total = round((50 * 24200 + 50 * 100) * 0.10, 2)
    assert approx(out[2] + out[3], group_total, tol=1.0)
    assert out[2] > out[3]  # future leg carries most of the notional weight
    # 2 groups (solo + basket) => 2 margin calls, NOT one per leg
    assert mkt.calls == 2, f"expected 2 netted calls, got {mkt.calls}"
    print(f"OK grouping: solo={out[1]:.0f}, basket split={out[2]:.0f}+{out[3]:.0f}={group_total:.0f}, calls={mkt.calls}")


if __name__ == "__main__":
    test_equity_unchanged()
    test_long_future_leverage()
    test_short_future_signs()
    test_margin_fallback_to_notional()
    test_resolve_grouping_and_split()
    print("\nALL LEVERAGE CHECKS PASSED")
