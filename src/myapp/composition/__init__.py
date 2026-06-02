"""组合根包：应用 wiring 与依赖注入。"""

from myapp.composition.dependencies import (
    check_database_ready,
    get_db_session,
    get_external_service,
    get_item_service,
)

__all__ = [
    "check_database_ready",
    "get_db_session",
    "get_external_service",
    "get_item_service",
]
