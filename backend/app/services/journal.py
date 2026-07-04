"""Trade journal performance math — pure, auditable.

Per closed trade:
    R-multiple = (exit - entry) / (entry - stop)      for a long
               = (entry - exit) / (stop - entry)      for a short
  i.e. profit measured in units of the risk you took. +2R means you made twice what
  you risked; -1R means you lost exactly your planned risk.

Across trades:
    win rate, average win/loss (rupees), average R, profit factor, and **expectancy**
    (expected rupees and R per trade) — so the user learns whether an edge is real.
"""

from __future__ import annotations

from datetime import date


def r_multiple(entry: float, stop: float, exit_price: float, side: str = "long") -> float | None:
    """Profit in units of initial risk. None if there is no defined risk (entry == stop)."""
    risk = abs(entry - stop)
    if risk == 0:
        return None
    move = (exit_price - entry) if side == "long" else (entry - exit_price)
    return round(move / risk, 3)


def trade_pnl(entry: float, exit_price: float, quantity: float, side: str = "long",
              fees: float = 0.0) -> float:
    """Realised rupee P&L of a closed trade, net of fees."""
    gross = (exit_price - entry) * quantity if side == "long" else (entry - exit_price) * quantity
    return round(gross - fees, 2)


def summarize(closed: list[dict]) -> dict:
    """Aggregate performance over closed trades.

    Each item needs: entry, stop, exit, quantity, side, fees.
    """
    if not closed:
        return {"count": 0, "wins": 0, "losses": 0, "win_rate_pct": 0.0, "avg_win": 0.0,
                "avg_loss": 0.0, "avg_r": 0.0, "total_pnl": 0.0, "expectancy_money": 0.0,
                "expectancy_r": 0.0, "profit_factor": None}

    pnls, rs = [], []
    for t in closed:
        pnls.append(trade_pnl(t["entry"], t["exit"], t["quantity"], t.get("side", "long"), t.get("fees", 0.0)))
        r = r_multiple(t["entry"], t["stop"], t["exit"], t.get("side", "long"))
        if r is not None:
            rs.append(r)

    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    n = len(pnls)
    win_rate = len(wins) / n * 100 if n else 0.0
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = sum(losses) / len(losses) if losses else 0.0  # negative
    total_pnl = sum(pnls)
    avg_r = sum(rs) / len(rs) if rs else 0.0
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else None

    # Expectancy: expected rupees per trade, and in R units.
    expectancy_money = total_pnl / n if n else 0.0

    return {
        "count": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round(win_rate, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "avg_r": round(avg_r, 3),
        "total_pnl": round(total_pnl, 2),
        "expectancy_money": round(expectancy_money, 2),
        "expectancy_r": round(avg_r, 3),
        "profit_factor": None if profit_factor is None else round(profit_factor, 2),
    }


# --------------------------------------------------------------------------- #
# Financial-year review (Indian FY = 1 Apr -> 31 Mar)
# --------------------------------------------------------------------------- #
def fy_start_year(d: date) -> int:
    """Indian financial-year start year for a date. Apr-Dec -> this year; Jan-Mar -> last year."""
    return d.year if d.month >= 4 else d.year - 1


def fy_label(start_year: int) -> str:
    """'FY2025-26' style label for a FY beginning in April of ``start_year``."""
    return f"FY{start_year}-{str(start_year + 1)[2:]}"


def fy_bounds(start_year: int) -> tuple[date, date]:
    return date(start_year, 4, 1), date(start_year + 1, 3, 31)


def fy_is_complete(start_year: int, today: date) -> bool:
    """A FY is analysable only once 31 Mar of its closing year has passed."""
    return today > date(start_year + 1, 3, 31)


def _allocation_guidance(by_segment: dict) -> dict | None:
    """Rule-based read on which segment earned best and whether capital should tilt.

    Educational, not advice: ranks segments by realised P&L + expectancy and points out
    the contributor and the drag. All numbers come from ``summarize`` — no AI here.
    """
    segs = [(b, s) for b, s in by_segment.items() if s.get("count")]
    if not segs:
        return None
    total = sum(s["total_pnl"] for _, s in segs)
    by_pnl = sorted(segs, key=lambda x: x[1]["total_pnl"], reverse=True)
    by_exp = sorted(segs, key=lambda x: x[1]["expectancy_money"], reverse=True)
    best_b, best_s = by_pnl[0]
    worst_b, worst_s = by_pnl[-1]
    exp_b, exp_s = by_exp[0]
    contributions = {b: (round(s["total_pnl"] / total * 100, 1) if total else None) for b, s in segs}

    obs: list[str] = []
    obs.append(f"{best_b} was your top segment - {round(best_s['total_pnl'])} across "
               f"{best_s['count']} trade(s) at a {best_s['win_rate_pct']}% win rate.")
    obs.append(f"Best expectancy: {exp_b} at {round(exp_s['expectancy_money'])} per trade "
               f"({exp_s['expectancy_r']}R).")
    if worst_b != best_b and worst_s["total_pnl"] < 0:
        obs.append(f"{worst_b} lost money ({round(worst_s['total_pnl'])}); review whether its "
                   f"capital share is justified by results.")
    if len(segs) > 1:
        obs.append(f"On these results, capital tilts toward {exp_b} (best risk-adjusted return) "
                   f"and away from the weakest segment - but one year is a small sample.")
    return {
        "best_segment": best_b,
        "worst_segment": worst_b,
        "best_expectancy_segment": exp_b,
        "contributions_pct": contributions,
        "observations": obs,
    }


def _to_date(v) -> date | None:
    if v is None:
        return None
    if isinstance(v, str):
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None
    return v


def review_financial_years(closed: list[dict], holdings: list[dict] | None = None,
                           today: date | None = None) -> dict:
    """Per-financial-year analysis combining realised trades and still-open holdings.

    Two inputs, two views per FY (Indian FY = 1 Apr -> 31 Mar):
      * ``closed`` - realised journal trades. Each needs entry/stop/exit/quantity/side/fees,
        bucket, exit_date. A trade counts in the FY it was *closed* (realised).
      * ``holdings`` - still-open positions from My Holdings (NOT journal entries). Each
        needs bucket, invested, unrealized_pnl, buy_date. A holding counts as *held at
        year-end* for every FY from the one it was bought in through the latest - so a
        long-term position bought once and held for years shows up in each of those years
        even though it was never closed (the user's "automatically in the calculation").

    Only COMPLETED financial years carry allocation guidance; the in-progress FY is flagged
    ``complete: false``. Holdings with no buy_date are treated as bought in the current FY.
    """
    today = today or date.today()
    holdings = holdings or []
    cur_year = fy_start_year(today)

    closed_by_year: dict[int, list[dict]] = {}
    for t in closed:
        ed = _to_date(t.get("exit_date"))
        if ed is None:
            continue
        closed_by_year.setdefault(fy_start_year(ed), []).append(t)

    parsed_holdings = []
    for h in holdings:
        bd = _to_date(h.get("buy_date"))
        parsed_holdings.append({**h, "_buy_fy": fy_start_year(bd) if bd else cur_year})

    activity = set(closed_by_year) | {h["_buy_fy"] for h in parsed_holdings}
    if not activity:
        return {"financial_years": [], "completed_count": 0,
                "current_fy": fy_label(cur_year), "comparison": []}

    years: list[dict] = []
    for sy in range(cur_year, min(activity) - 1, -1):
        complete = fy_is_complete(sy, today)
        trades = closed_by_year.get(sy, [])
        segs: dict[str, list[dict]] = {}
        for t in trades:
            segs.setdefault(t.get("bucket") or "unassigned", []).append(t)
        by_segment = {b: summarize(ts) for b, ts in segs.items()}

        # Open positions held at this FY's year-end (bought on/before it, still open today).
        held_by_segment: dict[str, dict] = {}
        for h in parsed_holdings:
            if h["_buy_fy"] > sy:
                continue
            g = held_by_segment.setdefault(h.get("bucket") or "unassigned",
                                           {"count": 0, "invested": 0.0, "unrealized_pnl": 0.0})
            g["count"] += 1
            g["invested"] += h.get("invested") or 0.0
            g["unrealized_pnl"] += h.get("unrealized_pnl") or 0.0
        for g in held_by_segment.values():
            g["invested"] = round(g["invested"], 2)
            g["unrealized_pnl"] = round(g["unrealized_pnl"], 2)
        held_total = {
            "count": sum(g["count"] for g in held_by_segment.values()),
            "invested": round(sum(g["invested"] for g in held_by_segment.values()), 2),
            "unrealized_pnl": round(sum(g["unrealized_pnl"] for g in held_by_segment.values()), 2),
        }

        start, end = fy_bounds(sy)
        years.append({
            "label": fy_label(sy),
            "start_year": sy,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "complete": complete,
            "overall": summarize(trades),
            "by_segment": by_segment,
            "held_by_segment": held_by_segment,
            "held_total": held_total,
            "guidance": _allocation_guidance(by_segment) if (complete and trades) else None,
        })

    # Cross-FY comparison: completed years that actually realised trades, newest first.
    completed_realised = [y for y in years if y["complete"] and y["overall"]["count"]]
    comparison = []
    for i, y in enumerate(completed_realised):
        prev = completed_realised[i + 1] if i + 1 < len(completed_realised) else None
        cur_pnl = y["overall"]["total_pnl"]
        prev_pnl = prev["overall"]["total_pnl"] if prev else None
        comparison.append({
            "label": y["label"],
            "total_pnl": cur_pnl,
            "win_rate_pct": y["overall"]["win_rate_pct"],
            "count": y["overall"]["count"],
            "best_segment": (y["guidance"] or {}).get("best_segment"),
            "pnl_change_vs_prev": (None if prev_pnl is None else round(cur_pnl - prev_pnl, 2)),
        })

    return {
        "financial_years": years,
        "completed_count": len([y for y in years if y["complete"]]),
        "current_fy": fy_label(cur_year),
        "comparison": comparison,
    }
