"""Angel One SmartAPI provider (live data, read-only).

Optional and **off by default** — the app runs fully on manually-entered holdings
(CSV/DB), with no broker connection. This provider only does anything when
``DATA_PROVIDER=angelone`` is explicitly set. Read-only by design: it would fetch
holdings/prices/history and never place orders.

The live price/history calls are intentionally left unimplemented: the product is
manual-first (the user enters holdings and current prices themselves). SmartApi +
pyotp are imported lazily so CSV mode never needs them installed.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from ..core.config import Settings
from .provider import Holding, MarketDataProvider, ProviderInfo


class AngelOneProvider(MarketDataProvider):
    name = "angelone"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None  # SmartConnect session, created on first use
        self._session = None

    # --- status -----------------------------------------------------------
    def info(self) -> ProviderInfo:
        if not self.settings.angel_configured:
            return ProviderInfo(
                name="Angel One SmartAPI",
                mode="live",
                ready=False,
                detail=(
                    "Angel One keys not set. Add ANGEL_* values to backend/.env to "
                    "enable the live feed."
                ),
            )
        return ProviderInfo(
            name="Angel One SmartAPI",
            mode="live",
            ready=True,
            detail="Credentials present. Live session is created on first request.",
        )

    # --- session ----------------------------------------------------------
    def _ensure_session(self):
        """Create (once) an authenticated SmartConnect session using TOTP login."""
        if self._client is not None:
            return self._client
        try:
            import pyotp
            from SmartApi import SmartConnect  # provided by smartapi-python
        except ImportError as exc:  # pragma: no cover - guidance path
            raise RuntimeError(
                "Live mode needs the SmartAPI SDK. Run: "
                "pip install smartapi-python pyotp"
            ) from exc

        s = self.settings
        client = SmartConnect(api_key=s.angel_api_key)
        totp = pyotp.TOTP(s.angel_totp_secret).now()
        self._session = client.generateSession(s.angel_client_code, s.angel_pin, totp)
        self._client = client
        return client

    # --- data methods -----------------------------------------------------
    def get_holdings(self) -> list[Holding]:
        client = self._ensure_session()
        raw = client.holding()  # SmartAPI read-only holdings call
        rows = (raw or {}).get("data") or []
        holdings: list[Holding] = []
        for r in rows:
            holdings.append(
                Holding(
                    symbol=str(r.get("tradingsymbol", "")).upper(),
                    quantity=float(r.get("quantity", 0) or 0),
                    avg_price=float(r.get("averageprice", 0) or 0),
                    ltp=float(r.get("ltp", 0) or 0),
                    bucket="unassigned",
                )
            )
        return holdings

    def get_ltp(self, symbol: str) -> float:
        # Not implemented: the product is manual-first (prices entered by the user).
        raise NotImplementedError("Live LTP lookup is not used — prices are entered manually.")

    def get_historical(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        # Not implemented: the product is manual-first (no broker history feed).
        raise NotImplementedError("Live history is not used — the app runs on manual data.")
