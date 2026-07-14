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
    # F&O leverage: the real SPAN+exposure margin Angel blocks for this leg (the capital
    # actually deployed), set by holdings.load_holdings when the live feed is available.
    # None for equity or when the feed is off -> capital falls back to full cost/notional.
    margin: float | None = None

    @property
    def invested(self) -> float:
        """Cost basis at the FULL contract value (notional). Unchanged — used where
        market exposure matters (hedge beta * exposure, risk/VaR)."""
        return self.quantity * self.avg_price

    @property
    def current_value(self) -> float:
        """Market value at the FULL contract value (notional). Hedge and risk read this,
        so it must stay the real market exposure, NOT the margin."""
        return self.quantity * self.ltp

    @property
    def pnl(self) -> float:
        """Unrealised P&L in rupees. Exact for F&O too (a future's rupee P&L is its
        notional change), and independent of how capital is measured."""
        raw = self.current_value - self.invested
        return raw if self.side != "sell" else -raw

    @property
    def pnl_pct(self) -> float:
        return (self.pnl / self.invested * 100.0) if self.invested else 0.0

    # --- leverage-aware capital view (My Holdings / Dashboard / Allocation) -----
    # F&O is leveraged: you only put up `margin`, not the full contract value. These
    # express the position against the capital actually deployed, so allocation % and
    # % return reflect reality instead of the notional. Equity has no margin, so they
    # collapse to the plain cost/market values.
    @property
    def capital(self) -> float:
        """Capital actually deployed: Angel margin for F&O, else cost (qty x avg)."""
        return self.margin if self.margin is not None else self.invested

    @property
    def capital_value(self) -> float:
        """Current worth of the deployed capital = capital + unrealised P&L.
        For equity this equals market value (qty x ltp)."""
        return self.capital + self.pnl

    @property
    def capital_pnl_pct(self) -> float:
        """% return on the capital actually deployed (leverage-aware for F&O)."""
        return (self.pnl / self.capital * 100.0) if self.capital else 0.0

    @property
    def leverage(self) -> float | None:
        """Notional / margin (e.g. 9.8x for a future). None for equity or unknown margin."""
        if self.kind != "EQ" and self.margin and self.margin > 0:
            return abs(self.current_value) / self.margin
        return None


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
