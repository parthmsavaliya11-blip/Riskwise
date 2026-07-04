"""Provider-pluggable AI explainers.

Each explainer takes a module name + the already-computed numbers and returns a
short, plain-language explanation. The hard rule (math engine vs. AI) is enforced in
the system prompt: use ONLY the figures provided, never produce new ones.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod

# One system prompt, shared across providers, that encodes the SEBI-safe framing and
# the "never invent numbers" rule.
SYSTEM_PROMPT = (
    "You are a concise financial educator for Indian retail investors. You are given "
    "numbers that a deterministic calculator already computed. Explain in plain, simple "
    "language what they mean and what the user should be aware of.\n"
    "STRICT RULES:\n"
    "1. Use ONLY the figures provided. Never compute, estimate, round differently, or "
    "invent any new number.\n"
    "2. This is education, NOT investment advice. Do not tell the user to buy or sell, "
    "and do not give price targets.\n"
    "3. Call out the single most important risk or caveat in the data.\n"
    "4. Be brief: at most ~140 words, plain words a beginner understands. Use rupees "
    "(Rs) and Indian market context. No markdown headers."
)

# Large arrays the model doesn't need (and which cost tokens) are dropped/truncated.
_DROP_KEYS = {"payoff_curve", "series", "matrix", "weights", "disclaimer"}
_MAX_LIST = 12


def _compact(obj):
    """Trim the payload so the prompt stays small and contains only relevant figures."""
    if isinstance(obj, dict):
        return {k: _compact(v) for k, v in obj.items() if k not in _DROP_KEYS}
    if isinstance(obj, list):
        return [_compact(x) for x in obj[:_MAX_LIST]]
    return obj


def build_prompt(module: str, data: dict) -> str:
    compact = _compact(data)
    return (
        f"Module: {module}\n"
        f"Already-computed results (JSON):\n{json.dumps(compact, ensure_ascii=False)}\n\n"
        "Explain these results for the user, following the rules."
    )


class Explainer(ABC):
    provider: str = "none"
    available: bool = False

    @abstractmethod
    def explain(self, module: str, data: dict) -> str: ...


class NoneExplainer(Explainer):
    provider = "none"
    available = False

    def explain(self, module: str, data: dict) -> str:
        return (
            "The AI explainer is turned off. Set AI_PROVIDER=gemini (free) and a "
            "GEMINI_API_KEY in backend/.env to get plain-language explanations. All the "
            "numbers above are computed without AI."
        )


class GeminiExplainer(Explainer):
    provider = "gemini"
    available = True

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model or "gemini-2.5-flash"

    def explain(self, module: str, data: dict) -> str:
        # Imported lazily so CSV/Claude installs don't need google-genai.
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=800,
            temperature=0.4,
        )
        # gemini-2.5-flash is a "thinking" model: on bigger prompts it spends most of
        # the output-token budget on internal reasoning and the visible reply gets
        # truncated (we saw an 80-char cut-off). This is a plain narration task, so
        # disable thinking to give the whole budget to the visible answer.
        try:
            config.thinking_config = types.ThinkingConfig(thinking_budget=0)
        except Exception:
            pass  # older SDKs without ThinkingConfig still work (just may think)

        resp = client.models.generate_content(
            model=self.model,
            contents=build_prompt(module, data),
            config=config,
        )
        return (resp.text or "").strip() or "The AI returned an empty response — try again."


class ClaudeExplainer(Explainer):
    provider = "claude"
    available = True

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model or "claude-sonnet-4-6"

    def explain(self, module: str, data: dict) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=self.api_key)
        resp = client.messages.create(
            model=self.model,
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": build_prompt(module, data)}],
        )
        return next((b.text for b in resp.content if b.type == "text"), "").strip()
