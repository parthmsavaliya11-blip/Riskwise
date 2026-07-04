"""Per-bucket portfolio scoping.

Lets the Hedge and Risk endpoints analyse one capital bucket at a time (e.g. just
Swing or just F&O) instead of the whole portfolio — so a user who holds long-term
stock through everything but trades swing/F&O aggressively can hedge and risk-check
each sub-portfolio on its own.
"""

from __future__ import annotations

from ..data.provider import Holding


def scope_holdings(
    holdings: list[Holding], bucket: str | None
) -> tuple[list[Holding], list[str], str | None]:
    """Filter holdings to one bucket (or all).

    Returns ``(filtered_holdings, available_buckets, selected_bucket)`` where
    ``selected_bucket`` is ``None`` for the whole portfolio.
    """
    available = sorted({h.bucket for h in holdings})
    selected = (bucket or "").strip()
    if not selected or selected.lower() == "all":
        return holdings, available, None
    return [h for h in holdings if h.bucket == selected], available, selected
