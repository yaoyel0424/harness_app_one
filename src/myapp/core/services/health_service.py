"""健康检查业务服务。"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from myapp.utils.logging import get_logger

logger = get_logger(__name__)


class HealthService:
    """健康检查服务，封装基础设施连通性检查。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def is_database_ready(self) -> bool:
        """检查数据库是否可以执行最小查询。"""
        try:
            await self._session.execute(text("SELECT 1"))
        except Exception:
            logger.warning("数据库就绪检查失败", exc_info=True)
            return False
        return True
