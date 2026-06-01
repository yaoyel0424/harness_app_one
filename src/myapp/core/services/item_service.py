"""Item 业务服务。"""

from myapp.db.repositories.item_repository import ItemRepository
from myapp.schemas.item import ItemCreate, ItemResponse


class ItemService:
    """Item 领域服务，封装业务规则。"""

    def __init__(self, repository: ItemRepository) -> None:
        self._repository = repository

    async def list_items(self) -> list[ItemResponse]:
        """获取全部 Item。"""
        items = await self._repository.list_items()
        return [ItemResponse.model_validate(item) for item in items]

    async def get_item(self, item_id: int) -> ItemResponse | None:
        """按 ID 获取 Item。"""
        item = await self._repository.get_by_id(item_id)
        if item is None:
            return None
        return ItemResponse.model_validate(item)

    async def create_item(self, payload: ItemCreate) -> ItemResponse:
        """创建 Item。"""
        item = await self._repository.create(payload.name, payload.description)
        return ItemResponse.model_validate(item)
