"""Deterministic quant engine.

Every number the product shows comes from a pure function in this package
(allocation drift, position size, XIRR, beta, payoff, VaR, ...). The AI layer in
``app.ai`` only *explains* these numbers — it never produces them.
"""
