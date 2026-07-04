"""AI explainer layer.

Pluggable like the data layer: ``get_explainer()`` returns the explainer for the
configured provider (``none`` | ``gemini`` | ``claude``). Provider SDKs are imported
lazily inside each class, so the unused one never needs installing.

The explainer ONLY narrates numbers the deterministic engine already produced — it
never computes or invents figures (enforced by the system prompt and by trimming the
payload to the already-computed results).
"""

from __future__ import annotations

from functools import lru_cache

from ..core.config import settings
from .explainer import ClaudeExplainer, Explainer, GeminiExplainer, NoneExplainer


@lru_cache
def get_explainer() -> Explainer:
    provider = (settings.ai_provider or "none").lower()
    if provider == "gemini" and settings.gemini_configured:
        return GeminiExplainer(settings.gemini_api_key, settings.gemini_model)
    if provider == "claude" and settings.anthropic_configured:
        return ClaudeExplainer(settings.anthropic_api_key, settings.anthropic_model)
    return NoneExplainer()


__all__ = ["get_explainer", "Explainer"]
