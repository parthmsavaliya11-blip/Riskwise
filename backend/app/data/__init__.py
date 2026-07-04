"""Data layer: provider factory.

``get_provider()`` returns the active provider based on settings, so the rest of
the app never imports a concrete broker class directly.
"""

from __future__ import annotations

from functools import lru_cache

from ..core.config import DATA_DIR, settings
from .csv_provider import CsvProvider
from .provider import Holding, MarketDataProvider, ProviderInfo

__all__ = ["get_provider", "MarketDataProvider", "Holding", "ProviderInfo"]


@lru_cache(maxsize=1)
def get_provider() -> MarketDataProvider:
    if settings.data_provider.lower() == "angelone":
        # Imported lazily so CSV mode never needs the SmartAPI SDK.
        from .angelone import AngelOneProvider

        return AngelOneProvider(settings)
    return CsvProvider(DATA_DIR)
