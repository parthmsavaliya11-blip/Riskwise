"""XIRR — money-weighted annualised return for irregular cash flows.

Used for per-bucket performance in Module 1: "which strategy actually earned the
best return", accounting for *when* money went in/out (a naive % return doesn't).

Self-contained (no external dependency): solves the standard XIRR equation

    sum_i  cf_i / (1 + r) ** (days_i / 365)  =  0

with Newton-Raphson and a bisection fallback so it is robust even when the
derivative misbehaves. Returns ``None`` when the cash flows can't yield a rate
(e.g. all same sign, or fewer than two flows) instead of raising.
"""

from __future__ import annotations

from datetime import date

CashFlow = tuple[date, float]  # (date, amount): +in to the strategy, -out


def _npv(rate: float, flows: list[CashFlow], t0: date) -> float:
    return sum(
        cf / (1.0 + rate) ** ((d - t0).days / 365.0) for d, cf in flows
    )


def _npv_derivative(rate: float, flows: list[CashFlow], t0: date) -> float:
    total = 0.0
    for d, cf in flows:
        years = (d - t0).days / 365.0
        total -= years * cf / (1.0 + rate) ** (years + 1.0)
    return total


def xirr(flows: list[CashFlow], guess: float = 0.1) -> float | None:
    """Annualised money-weighted rate as a decimal (0.18 == 18%), or None."""
    if len(flows) < 2:
        return None
    # Need both an inflow and an outflow, otherwise no root exists.
    has_pos = any(cf > 0 for _, cf in flows)
    has_neg = any(cf < 0 for _, cf in flows)
    if not (has_pos and has_neg):
        return None

    flows = sorted(flows, key=lambda f: f[0])
    t0 = flows[0][0]

    # --- Newton-Raphson ---
    rate = guess
    for _ in range(100):
        try:
            value = _npv(rate, flows, t0)
            deriv = _npv_derivative(rate, flows, t0)
        except (OverflowError, ZeroDivisionError):
            break
        if abs(value) < 1e-7:
            return rate
        if deriv == 0:
            break
        new_rate = rate - value / deriv
        if new_rate <= -0.999999:  # keep (1+r) positive
            new_rate = (rate - 0.999999) / 2.0
        if abs(new_rate - rate) < 1e-9:
            return new_rate
        rate = new_rate

    # --- Bisection fallback over a wide sane range (-99% .. +1000%) ---
    lo, hi = -0.999999, 10.0
    try:
        f_lo, f_hi = _npv(lo, flows, t0), _npv(hi, flows, t0)
    except OverflowError:
        return None
    if f_lo * f_hi > 0:
        return None  # no sign change -> no root in range
    for _ in range(200):
        mid = (lo + hi) / 2.0
        f_mid = _npv(mid, flows, t0)
        if abs(f_mid) < 1e-7:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0
