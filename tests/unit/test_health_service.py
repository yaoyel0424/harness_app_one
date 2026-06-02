"""健康检查服务单元测试。"""

from unittest.mock import AsyncMock

import pytest

from myapp.core.services.health_service import HealthService


class FailingSession:
    """测试用会话，模拟数据库查询失败。"""

    async def execute(self, statement: object) -> None:
        """模拟 SQL 执行异常。"""
        _ = statement
        raise RuntimeError("数据库不可用")


@pytest.mark.asyncio
async def test_health_service_database_ready() -> None:
    """数据库查询成功时应返回 ready。"""
    session = AsyncMock()
    service = HealthService(session)

    assert await service.is_database_ready() is True
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_health_service_database_unavailable() -> None:
    """数据库查询失败时应返回 not ready。"""
    service = HealthService(FailingSession())

    assert await service.is_database_ready() is False
