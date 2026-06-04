"""健康检查路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from myapp.composition.dependencies import get_health_service
from myapp.config import Settings, get_settings
from myapp.core.services.health_service import HealthService
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
    health_service: Annotated[HealthService, Depends(get_health_service)],
) -> HealthResponse:
    """就绪探针：检查数据库连通性。"""
    if not await health_service.is_database_ready():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="not_ready", service=settings.app_name)
    return HealthResponse(status="ready", service=settings.app_name)
