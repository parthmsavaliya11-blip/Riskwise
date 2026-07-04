"""Generate sample daily price history for offline (CSV-mode) testing.

Writes data/history/<SYMBOL>.csv (columns: date, close) for each holding plus the
NIFTY and BANKNIFTY indices. Each stock's returns are built as
``beta * index_return + idiosyncratic noise`` so the beta engine recovers a known
target beta (within noise) — that's what verify_phase2.py checks.

Reproducible (fixed seed). Run from backend/:
    .venv\\Scripts\\Activate.ps1
    python generate_sample_history.py

ASCII-only prints (Windows cp1252 console).
"""

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HISTORY_DIR = PROJECT_ROOT / "data" / "history"

N_RETURNS = 260  # ~1 trading year -> 261 closes
SEED = 42

# symbol -> (target beta vs NIFTY, last close = current ltp, idiosyncratic vol)
STOCKS = {
    "RELIANCE": (1.05, 2890.75, 0.009),
    "HDFCBANK": (1.15, 1480.30, 0.009),
    "TCS": (0.75, 3825.10, 0.008),
    "TATAMOTORS": (1.55, 695.40, 0.013),
    "ICICIBANK": (1.20, 1055.60, 0.009),
    "INFY": (0.80, 1512.25, 0.008),
    "NIFTY24JUNFUT": (1.00, 23615.00, 0.001),  # a NIFTY future ~ moves with NIFTY
}
INDEX_LAST = {"NIFTY": 23500.00, "BANKNIFTY": 51000.00, "SENSEX": 77000.00}


def price_path(returns: np.ndarray, last_close: float) -> np.ndarray:
    """Build a price path from returns, scaled so the final close == last_close."""
    path = np.empty(len(returns) + 1)
    path[0] = 100.0
    for i, r in enumerate(returns):
        path[i + 1] = path[i] * (1.0 + r)
    return path * (last_close / path[-1])


def write_csv(symbol: str, dates, closes) -> None:
    df = pd.DataFrame({"date": dates, "close": np.round(closes, 2)})
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(HISTORY_DIR / f"{symbol}.csv", index=False)
    print("wrote", symbol, "->", len(df), "rows, last close", round(closes[-1], 2))


def main() -> None:
    rng = np.random.default_rng(SEED)
    dates = pd.bdate_range(end="2026-06-18", periods=N_RETURNS + 1).strftime("%Y-%m-%d")

    # Market factor (NIFTY daily returns): ~10% annual drift, ~16% annual vol.
    nifty_ret = rng.normal(0.0004, 0.01, N_RETURNS)
    write_csv("NIFTY", dates, price_path(nifty_ret, INDEX_LAST["NIFTY"]))

    # BANKNIFTY: correlated with NIFTY but with its own kick (banks are higher-beta).
    bank_ret = 1.2 * nifty_ret + rng.normal(0.0001, 0.006, N_RETURNS)
    write_csv("BANKNIFTY", dates, price_path(bank_ret, INDEX_LAST["BANKNIFTY"]))

    for symbol, (beta, last_close, idio) in STOCKS.items():
        stock_ret = beta * nifty_ret + rng.normal(0.0, idio, N_RETURNS)
        write_csv(symbol, dates, price_path(stock_ret, last_close))

    # SENSEX: broad-market, moves very closely with NIFTY (a touch less volatile).
    # Drawn last so the NIFTY/BANKNIFTY/stock series above stay byte-identical.
    sensex_ret = 0.98 * nifty_ret + rng.normal(0.0001, 0.003, N_RETURNS)
    write_csv("SENSEX", dates, price_path(sensex_ret, INDEX_LAST["SENSEX"]))

    print("\nDone. Sample history is in", HISTORY_DIR)


if __name__ == "__main__":
    main()
