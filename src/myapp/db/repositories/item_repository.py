"""Item 仓储实现。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from myapp.db.models import ItemModel


class ItemRepository:
    """Item 数据访问对象。"""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_items(self) -> list[ItemModel]:
        """查询全部 Item。"""
        result = await self._session.execute(select(ItemModel).order_by(ItemModel.id))
        return list(result.scalars().all())

    async def get_by_id(self, item_id: int) -> ItemModel | None:
        """按 ID 查询 Item。"""
        return await self._session.get(ItemModel, item_id)

    async def create(self, name: str, description: str | None) -> ItemModel:
        """创建 Item。"""
        item = ItemModel(name=name, description=description)
        self._session.add(item)
        await self._session.commit()
        await self._session.refresh(item)
        return item
