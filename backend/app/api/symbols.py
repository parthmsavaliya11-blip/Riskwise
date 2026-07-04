"""Symbol autocomplete for the add-holding form (offline curated list)."""

from __future__ import annotations

from fastapi import APIRouter

from ..data.symbols import search_symbols

router = APIRouter(prefix="/api", tags=["symbols"])


@router.get("/symbols")
def get_symbols(q: str | None = None, limit: int = 50) -> dict:
    return {"symbols": search_symbols(q, limit)}
