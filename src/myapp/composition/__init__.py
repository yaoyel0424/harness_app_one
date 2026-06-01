"""组合根包：应用 wiring 与依赖注入。"""

from myapp.composition.dependencies import (
    get_db_session,
    get_external_service,
    get_item_service,
)

__all__ = ["get_db_session", "get_external_service", "get_item_service"]
