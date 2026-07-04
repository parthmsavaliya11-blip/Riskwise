"""Status endpoint: which data mode is active and what's configured."""

from __future__ import annotations

from fastapi import APIRouter

from ..core.config import settings
from ..data import get_provider

router = APIRouter(prefix="/api", tags=["status"])


@router.get("/status")
def get_status() -> dict:
    provider = get_provider()
    info = provider.info()
    return {
        "app": settings.app_name,
        "environment": settings.environment,
        "data_provider": {
            "name": info.name,
            "mode": info.mode,
            "ready": info.ready,
            "detail": info.detail,
        },
        "ai_provider": settings.ai_provider,
        "ai_explainer_configured": settings.ai_configured,
        "angel_configured": settings.angel_configured,
    }
