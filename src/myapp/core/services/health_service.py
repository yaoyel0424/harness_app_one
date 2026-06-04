"""健康检查业务服务。"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from myapp.utils.logging import get_logger

logger = get_logger(__name__)


class HealthService:
    """封装健康检查所需的业务逻辑。"""

    def __init__(self, session: AsyncSession) -> None:
        """初始化健康检查服务。"""
        self._session = session

    async def is_database_ready(self) -> bool:
        """检查数据库是否可执行最小查询。"""
        try:
            await self._session.execute(text("SELECT 1"))
        except Exception as exc:
            logger.warning(
                "数据库就绪检查失败",
                extra={"exception_type": type(exc).__name__},
            )
            return False
        return True
