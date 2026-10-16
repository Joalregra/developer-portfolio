"""Liveness route. It never calls the LLM providers or the database, so it costs no quota."""

from fastapi import APIRouter

from app.api.deps import KnowledgeDep, SettingsDep
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", summary="Check that the API process is alive")
async def health(settings: SettingsDep, knowledge: KnowledgeDep) -> HealthResponse:
    return HealthResponse(
        status="ok", environment=settings.environment, knowledge_version=knowledge.version
    )
