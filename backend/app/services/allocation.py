"""Capital allocation tracker — pure, auditable math.

Takes the investor's holdings (grouped by bucket) and their target split, and
reports current allocation %, drift vs target, whether each bucket is inside its
tolerance band, and the rupee amount to add/trim to get back to target.

No I/O here: callers pass plain data in and get plain dicts out, so this is
trivially unit-testable and matches a hand/spreadsheet calculation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BucketTarget:
    """A configured allocation bucket: a name, a target %, and a tolerance band."""

    name: str
    target_pct: float
    tolerance_pct: float = 5.0


@dataclass
class BucketActual:
    """What the investor actually holds in a bucket right now."""

    name: str
    current_value: float
    invested: float = 0.0

    @property
    def pnl(self) -> float:
        return self.current_value - self.invested


def _status(drift_pct: float, tolerance_pct: float) -> str:
    """Classify a bucket relative to its tolerance band.

    ``drift_pct`` is (current% - target%). Positive => overweight.
    """
    if abs(drift_pct) <= tolerance_pct:
        return "in-band"
    return "over" if drift_pct > 0 else "under"


def analyze_allocation(
    targets: list[BucketTarget],
    actuals: list[BucketActual],
) -> dict:
    """Combine targets + actuals into a full allocation report.

    Buckets that exist in holdings but were never configured are surfaced with a
    0% target and flagged ``untracked`` so nothing is silently hidden. Configured
    buckets with no holdings show up at 0% so the user sees the gap to fill.
    """
    actual_by_name = {a.name: a for a in actuals}
    target_by_name = {t.name: t for t in targets}

    total_value = sum(a.current_value for a in actuals)
    target_sum = round(sum(t.target_pct for t in targets), 2)

    # Union of configured + held bucket names, configured order first.
    names: list[str] = [t.name for t in targets]
    for a in actuals:
        if a.name not in target_by_name:
            names.append(a.name)

    rows: list[dict] = []
    any_drifted = False
    for name in names:
        target = target_by_name.get(name)
        actual = actual_by_name.get(name)

        current_value = actual.current_value if actual else 0.0
        invested = actual.invested if actual else 0.0
        current_pct = (current_value / total_value * 100.0) if total_value else 0.0

        target_pct = target.target_pct if target else 0.0
        tolerance_pct = target.tolerance_pct if target else 0.0
        tracked = target is not None

        drift_pct = current_pct - target_pct
        target_value = total_value * target_pct / 100.0
        # +ve => add money to this bucket; -ve => trim it.
        rebalance_value = target_value - current_value

        status = _status(drift_pct, tolerance_pct) if tracked else "untracked"
        if tracked and status != "in-band":
            any_drifted = True

        rows.append(
            {
                "bucket": name,
                "tracked": tracked,
                "current_value": round(current_value, 2),
                "invested": round(invested, 2),
                "pnl": round(current_value - invested, 2),
                "current_pct": round(current_pct, 2),
                "target_pct": round(target_pct, 2),
                "tolerance_pct": round(tolerance_pct, 2),
                "drift_pct": round(drift_pct, 2),
                "target_value": round(target_value, 2),
                "rebalance_value": round(rebalance_value, 2),
                "status": status,
            }
        )

    # Targets should sum to 100%. If they don't, the user's plan is incomplete;
    # we report it rather than silently normalising.
    targets_valid = abs(target_sum - 100.0) < 0.01 if targets else False

    return {
        "rows": rows,
        "total_value": round(total_value, 2),
        "target_sum_pct": target_sum,
        "targets_valid": targets_valid,
        "any_drifted": any_drifted,
        "bucket_count": len(rows),
    }
