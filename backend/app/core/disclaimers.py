"""SEBI-safe framing.

This product is an *educational / analytical decision-support* tool. It does NOT
give investment advice and never places orders. Every analytical response carries
the disclaimer below.
"""

DISCLAIMER = (
    "For educational and informational purposes only. This is not investment "
    "advice or a recommendation to buy or sell any security. All figures are "
    "estimates based on the data and assumptions you provide. Markets carry risk; "
    "consult a SEBI-registered adviser before acting. You place all orders yourself "
    "through your broker."
)


def with_disclaimer(payload: dict) -> dict:
    """Attach the standard disclaimer to any API response payload."""
    out = dict(payload)
    out["disclaimer"] = DISCLAIMER
    return out
