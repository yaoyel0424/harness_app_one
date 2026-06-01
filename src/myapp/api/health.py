"""健康检查路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from myapp.composition.dependencies import get_db_session
from myapp.config import Settings, get_settings
from myapp.schemas.item import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=HealthResponse)
async def liveness(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """存活探针：进程正常运行即返回 200。"""
    return HealthResponse(status="alive", service=settings.app_name)


@router.get("/health/ready", response_model=HealthResponse)
async def readiness(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> HealthResponse:
    """就绪探针：检查数据库连通性。"""
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="not_ready", service=settings.app_name)
    return HealthResponse(status="ready", service=settings.app_name)
