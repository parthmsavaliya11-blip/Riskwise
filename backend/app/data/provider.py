"""Market-data provider interface.

Every module reads prices, holdings and history through this single interface, so
we can swap brokers (or fall back to CSV) without touching business logic. This is
also the natural seam for per-user broker credentials when we go multi-user.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date

import pandas as pd


@dataclass
class Holding:
    """A single position the investor holds."""

    symbol: str
    quantity: float
    avg_price: float
    ltp: float = 0.0
    bucket: str = "unassigned"
    side: str = "buy"  # buy (long) | sell (short) — short F&O legs profit when price falls
    # Instrument identity (when known) so modules can resolve live data — e.g. the
    # hedge module fetches real historical candles by token to compute beta.
    token: str | None = None
    exchange: str | None = None
    kind: str = "EQ"  # EQ / FUT / CE / PE
    # Display grouping only: legs of one saved basket share these (see Position).
    basket_id: str | None = None
    basket_label: str | None = None

    @property
    def invested(self) -> float:
        return self.quantity * self.avg_price

    @property
    def current_value(self) -> float:
        return self.quantity * self.ltp

    @property
    def pnl(self) -> float:
        raw = self.current_value - self.invested
        return raw if self.side != "sell" else -raw

    @property
    def pnl_pct(self) -> float:
        return (self.pnl / self.invested * 100.0) if self.invested else 0.0


@dataclass
class ProviderInfo:
    """Describes which provider is active and whether it is ready."""

    name: str
    mode: str  # "offline" | "live"
    ready: bool
    detail: str = ""
    extras: dict = field(default_factory=dict)


class MarketDataProvider(ABC):
    """Abstract base every concrete provider implements."""

    name: str = "base"

    @abstractmethod
    def info(self) -> ProviderInfo:
        """Return current status (used by the /api/status endpoint)."""

    @abstractmethod
    def get_holdings(self) -> list[Holding]:
        """Return the investor's current holdings with live LTP filled in."""

    @abstractmethod
    def get_ltp(self, symbol: str) -> float:
        """Return the last traded price for a symbol."""

    @abstractmethod
    def get_historical(
        self, symbol: str, start: date, end: date
    ) -> pd.DataFrame:
        """Return daily history as a DataFrame indexed by date with a 'close' column.

        Used for beta, correlation, VaR and drawdown calculations.
        """
