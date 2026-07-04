"""SQLAlchemy models.

Every table carries ``user_id`` from day one (defaulting to the single local user)
so the move to multi-user later is additive, not a rewrite.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from ..core.config import settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Bucket(Base):
    """A capital allocation bucket (e.g. F&O 20%, Long-term 30%, Swing 50%)."""

    __tablename__ = "buckets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), default=settings.default_user_id, index=True)
    name: Mapped[str] = mapped_column(String(64))
    target_pct: Mapped[float] = mapped_column(Float, default=0.0)
    tolerance_pct: Mapped[float] = mapped_column(Float, default=5.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class Position(Base):
    """A holding the user entered manually — their real portfolio, tagged to a bucket.

    When the user has any positions, these become the source of truth for every module
    (allocation, hedge, risk, ...) instead of the sample CSV. Live LTP still comes from
    the market-data provider; ``ltp`` here is an optional manual current price for offline
    use.
    """

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), default=settings.default_user_id, index=True)
    symbol: Mapped[str] = mapped_column(String(32))           # display/underlying symbol
    bucket: Mapped[str] = mapped_column(String(64), default="Long-term")
    quantity: Mapped[float] = mapped_column(Float, default=0.0)  # total units (lots x lot_size for F&O)
    avg_price: Mapped[float] = mapped_column(Float, default=0.0)
    ltp: Mapped[float | None] = mapped_column(Float, nullable=True)  # optional manual current price
    buy_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    # Instrument details (filled from the market feed when picked from search) so live
    # price resolves directly and F&O lots/lot-size are known.
    tradingsymbol: Mapped[str | None] = mapped_column(String(64), nullable=True)
    exchange: Mapped[str | None] = mapped_column(String(8), nullable=True)   # NSE/BSE/NFO/BFO
    token: Mapped[str | None] = mapped_column(String(24), nullable=True)     # Angel instrument token
    lot_size: Mapped[int] = mapped_column(Integer, default=1)
    kind: Mapped[str] = mapped_column(String(8), default="EQ")               # EQ/FUT/CE/PE
    side: Mapped[str] = mapped_column(String(8), default="buy")              # buy (long) | sell (short)
    # Legs saved together from the Basket Order page share a basket_id (+ a human
    # basket_label) so the UI shows them as ONE grouped holding. Display-only — every
    # module still reads each leg individually (beta/VaR/payoff need the separate legs).
    basket_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    basket_label: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Trade(Base):
    """A logged trade for the journal (R-multiples, win rate, expectancy)."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), default=settings.default_user_id, index=True)
    symbol: Mapped[str] = mapped_column(String(32))
    bucket: Mapped[str] = mapped_column(String(64), default="unassigned")
    side: Mapped[str] = mapped_column(String(8), default="long")  # long | short
    entry_price: Mapped[float] = mapped_column(Float, default=0.0)
    stop_price: Mapped[float] = mapped_column(Float, default=0.0)
    target_price: Mapped[float] = mapped_column(Float, default=0.0)
    exit_price: Mapped[float] = mapped_column(Float, default=0.0)
    quantity: Mapped[float] = mapped_column(Float, default=0.0)
    fees: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(8), default="open")  # open | closed
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class CashFlow(Base):
    """Deposits / withdrawals / realized P&L per bucket, used for XIRR."""

    __tablename__ = "cash_flows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), default=settings.default_user_id, index=True)
    bucket: Mapped[str] = mapped_column(String(64), default="unassigned")
    amount: Mapped[float] = mapped_column(Float, default=0.0)  # +in / -out
    flow_date: Mapped[datetime] = mapped_column(DateTime, default=_now)
    note: Mapped[str] = mapped_column(String(255), default="")


__all__ = ["Base", "Bucket", "Position", "Trade", "CashFlow"]
