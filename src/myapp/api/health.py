"""健康检查路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from myapp.composition.dependencies import check_database_ready
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
    database_ready: Annotated[bool, Depends(check_database_ready)],
) -> HealthResponse:
    """就绪探针：检查数据库连通性。"""
    if not database_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="not_ready", service=settings.app_name)
    return HealthResponse(status="ready", service=settings.app_name)
