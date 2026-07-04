"""Offline CSV / manual provider.

Lets the whole product run and be tested with no broker connection. Reads simple
CSV files from the project ``data/`` directory:

* ``holdings.csv``  -> columns: symbol, quantity, avg_price, bucket
* ``prices.csv``    -> columns: symbol, ltp
* ``history/<SYMBOL>.csv`` -> columns: date, close  (optional, for beta/VaR)

All files are optional; missing data degrades gracefully rather than crashing.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from .provider import Holding, MarketDataProvider, ProviderInfo


class CsvProvider(MarketDataProvider):
    name = "csv"

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.holdings_file = self.data_dir / "holdings.csv"
        self.prices_file = self.data_dir / "prices.csv"
        self.history_dir = self.data_dir / "history"

    # --- status -----------------------------------------------------------
    def info(self) -> ProviderInfo:
        has_holdings = self.holdings_file.exists()
        return ProviderInfo(
            name="CSV / manual",
            mode="offline",
            ready=has_holdings,
            detail=(
                "Reading from local CSV files."
                if has_holdings
                else "No holdings.csv yet — upload or create one in the data/ folder."
            ),
            extras={
                "holdings_file": str(self.holdings_file),
                "prices_file": str(self.prices_file),
            },
        )

    # --- prices -----------------------------------------------------------
    def _price_map(self) -> dict[str, float]:
        if not self.prices_file.exists():
            return {}
        df = pd.read_csv(self.prices_file)
        df.columns = [c.strip().lower() for c in df.columns]
        return {
            str(r["symbol"]).strip().upper(): float(r["ltp"])
            for _, r in df.iterrows()
            if pd.notna(r.get("ltp"))
        }

    def get_ltp(self, symbol: str) -> float:
        return self._price_map().get(symbol.strip().upper(), 0.0)

    # --- holdings ---------------------------------------------------------
    def get_holdings(self) -> list[Holding]:
        if not self.holdings_file.exists():
            return []
        df = pd.read_csv(self.holdings_file)
        df.columns = [c.strip().lower() for c in df.columns]
        prices = self._price_map()

        holdings: list[Holding] = []
        for _, r in df.iterrows():
            symbol = str(r["symbol"]).strip().upper()
            avg_price = float(r.get("avg_price", 0) or 0)
            # Use a live/last price if we have one, else fall back to avg cost.
            ltp = prices.get(symbol, avg_price)
            holdings.append(
                Holding(
                    symbol=symbol,
                    quantity=float(r.get("quantity", 0) or 0),
                    avg_price=avg_price,
                    ltp=ltp,
                    bucket=str(r.get("bucket", "unassigned") or "unassigned").strip(),
                )
            )
        return holdings

    # --- history ----------------------------------------------------------
    def get_historical(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        path = self.history_dir / f"{symbol.strip().upper()}.csv"
        if not path.exists():
            return pd.DataFrame(columns=["close"])
        df = pd.read_csv(path)
        df.columns = [c.strip().lower() for c in df.columns]
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        mask = (df.index.date >= start) & (df.index.date <= end)
        return df.loc[mask, ["close"]]
