"""AI explainer endpoint.

`POST /api/ai/explain` takes a module name + the already-computed numbers and returns
a plain-language explanation. The numbers always come from the deterministic services;
this only narrates them. Failures degrade gracefully (the UI still shows the figures).
"""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from ..ai import get_explainer
from ..core.config import settings
from ..core.disclaimers import with_disclaimer

router = APIRouter(prefix="/api/ai", tags=["ai"])


class ExplainRequest(BaseModel):
    module: str
    data: dict


@router.get("/status")
def ai_status() -> dict:
    return {
        "provider": settings.ai_provider,
        "configured": settings.ai_configured,
    }


@router.post("/explain")
def explain(req: ExplainRequest) -> dict:
    explainer = get_explainer()
    if not explainer.available:
        return with_disclaimer(
            {"available": False, "provider": settings.ai_provider, "text": explainer.explain(req.module, req.data)}
        )
    try:
        text = explainer.explain(req.module, req.data)
        return with_disclaimer({"available": True, "provider": explainer.provider, "text": text})
    except Exception as e:  # network/quota/SDK issues shouldn't break the page
        return with_disclaimer(
            {
                "available": True,
                "provider": explainer.provider,
                "error": True,
                "text": f"Couldn't reach the AI explainer ({type(e).__name__}). "
                "The figures above are still valid — they come from the calculator, not the AI.",
            }
        )
