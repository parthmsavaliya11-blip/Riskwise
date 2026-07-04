"""Position-sizing calculator — the headline risk tool.

Answers "how many shares / lots can I buy without risking more than my rule
allows?" using the classic fixed-fractional rule:

    risk budget        = account_size * risk_per_trade%        (e.g. 1-2% of capital)
    per-unit risk      = |entry - stop|
    max quantity       = floor(risk budget / per-unit risk)    (rounded to whole lots
                                                                 when a lot size is given)

Pure function: no I/O, so the worked example in the README/verification matches
this exactly.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import floor


@dataclass
class SizingInput:
    account_size: float
    risk_per_trade_pct: float
    entry_price: float
    stop_price: float
    side: str = "long"            # "long" | "short"
    lot_size: int = 1             # F&O lot size; 1 for cash equity
    bucket_room: float | None = None  # optional ₹ cap from the bucket's free space


def size_position(inp: SizingInput) -> dict:
    """Return max quantity/lots plus the rupee risk, value and any warnings."""
    warnings: list[str] = []

    account_size = max(inp.account_size, 0.0)
    risk_pct = max(inp.risk_per_trade_pct, 0.0)
    entry = inp.entry_price
    stop = inp.stop_price
    lot_size = max(int(inp.lot_size or 1), 1)

    risk_budget = account_size * risk_pct / 100.0
    per_unit_risk = abs(entry - stop)

    # Guardrails on the inputs themselves.
    if entry <= 0:
        return _error("Entry price must be greater than zero.")
    if per_unit_risk <= 0:
        return _error("Stop-loss must be different from entry so there is a defined risk.")
    if risk_budget <= 0:
        return _error("Account size and risk-per-trade % must both be greater than zero.")

    # A long should stop below entry; a short should stop above. Flag an inverted
    # stop but still compute on the distance so the tool stays useful.
    side = (inp.side or "long").lower()
    if side == "long" and stop >= entry:
        warnings.append("For a long trade the stop is usually below the entry price.")
    if side == "short" and stop <= entry:
        warnings.append("For a short trade the stop is usually above the entry price.")

    raw_qty = risk_budget / per_unit_risk
    lots = floor(raw_qty / lot_size)
    quantity = lots * lot_size

    if quantity <= 0:
        warnings.append(
            "Risk budget is too small for even one lot at this stop distance — "
            "widen the stop, raise risk %, or pick a smaller-lot instrument."
        )

    position_value = quantity * entry
    actual_risk = quantity * per_unit_risk
    risk_pct_of_account = (actual_risk / account_size * 100.0) if account_size else 0.0
    stop_distance_pct = (per_unit_risk / entry * 100.0) if entry else 0.0

    if position_value > account_size and account_size:
        warnings.append(
            "Position value exceeds your account size — this needs leverage/margin; "
            "make sure your broker margin allows it."
        )
    if inp.bucket_room is not None and position_value > inp.bucket_room:
        warnings.append(
            "Position value exceeds this bucket's remaining room versus its target "
            "allocation."
        )

    return {
        "ok": True,
        "quantity": quantity,
        "lots": lots,
        "lot_size": lot_size,
        "per_unit_risk": round(per_unit_risk, 2),
        "risk_budget": round(risk_budget, 2),
        "actual_risk": round(actual_risk, 2),
        "risk_pct_of_account": round(risk_pct_of_account, 3),
        "position_value": round(position_value, 2),
        "stop_distance_pct": round(stop_distance_pct, 2),
        "warnings": warnings,
    }


def _error(message: str) -> dict:
    return {
        "ok": False,
        "error": message,
        "quantity": 0,
        "lots": 0,
        "warnings": [],
    }
