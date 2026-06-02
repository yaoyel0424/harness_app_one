"""健康检查服务单元测试。"""

import logging
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from myapp.core.services.health_service import HealthService


class SuccessfulSession:
    """用于模拟可用数据库会话。"""

    def __init__(self) -> None:
        self.statements: list[str] = []

    async def execute(self, statement: object) -> None:
        """记录执行过的 SQL 语句。"""
        self.statements.append(str(statement))


class FailingSession:
    """用于模拟数据库执行失败的会话。"""

    async def execute(self, statement: object) -> None:
        """模拟数据库连接或查询异常。"""
        _ = statement
        raise RuntimeError("数据库不可用")


@pytest.mark.asyncio
async def test_health_service_database_ready() -> None:
    """数据库查询成功时应返回 True。"""
    session = SuccessfulSession()
    service = HealthService(cast(AsyncSession, session))

    assert await service.is_database_ready() is True
    assert session.statements == ["SELECT 1"]


@pytest.mark.asyncio
async def test_health_service_database_unready(caplog) -> None:
    """数据库查询失败时应记录日志并返回 False。"""
    caplog.set_level(logging.WARNING)
    service = HealthService(cast(AsyncSession, FailingSession()))

    assert await service.is_database_ready() is False
    assert "数据库就绪检查失败" in caplog.text
