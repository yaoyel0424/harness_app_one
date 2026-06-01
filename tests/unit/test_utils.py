"""OpenTelemetry 与日志工具测试。"""

import logging

from myapp.config import Settings
from myapp.utils.logging import get_logger, setup_logging
from myapp.utils.telemetry import setup_telemetry


def test_setup_logging_json_format(capsys) -> None:
    """setup_logging 应配置 JSON 格式输出。"""
    setup_logging("INFO")
    logger = get_logger("test")
    logger.info("测试消息", extra={"key": "value"})
    captured = capsys.readouterr()
    assert "测试消息" in captured.out or "message" in captured.out


def test_setup_telemetry_disabled() -> None:
    """OTel 未启用时不应抛异常。"""
    settings = Settings(otel_enabled=False)
    setup_telemetry(object(), settings, None)


def test_get_logger_returns_logger() -> None:
    """get_logger 应返回 logging.Logger 实例。"""
    logger = get_logger(__name__)
    assert isinstance(logger, logging.Logger)
