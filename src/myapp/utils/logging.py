"""日志工具模块。"""

import logging
import os
import sys
from pathlib import Path
from typing import Any

from pythonjsonlogger.json import JsonFormatter


def setup_logging(level: str = "INFO") -> None:
    """配置根日志器，输出 JSON 格式日志供 Loki 采集。"""
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level.upper())

    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level"},
    )

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    root.addHandler(stdout_handler)

    # 可选: 写入 JSONL 供 Promtail/Loki 采集 (LOG_FILE=logs/myapp.jsonl)
    log_file = os.getenv("LOG_FILE", "")
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """获取命名日志器。"""
    return logging.getLogger(name)


def log_extra(**kwargs: Any) -> dict[str, Any]:
    """构造结构化日志附加字段。"""
    return kwargs
