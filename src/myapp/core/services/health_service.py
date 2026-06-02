"""健康检查业务服务。"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class HealthService:
    """健康检查服务，封装运行时依赖连通性检测。"""

    def __init__(self, session: AsyncSession) -> None:
        """初始化健康检查服务。"""
        self._session = session

    async def is_database_ready(self) -> bool:
        """检查数据库是否可执行最小查询。"""
        try:
            await self._session.execute(text("SELECT 1"))
        except Exception:
            return False
        return True
