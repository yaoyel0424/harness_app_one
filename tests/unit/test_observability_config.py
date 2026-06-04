"""可观测性配置测试。"""

from pathlib import Path
from typing import Any, cast

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_yaml(path: Path) -> dict[str, Any]:
    """读取 YAML 配置并返回字典结构。"""
    content = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(content, dict)
    return cast("dict[str, Any]", content)


def test_prometheus_can_resolve_host_docker_internal_on_linux() -> None:
    """Prometheus 容器应在 Linux 上能解析宿主机访问别名。"""
    compose = _load_yaml(PROJECT_ROOT / "docker-compose.observability.yml")
    prometheus = compose["services"]["prometheus"]

    assert "host.docker.internal:host-gateway" in prometheus["extra_hosts"]


def test_prometheus_scrape_target_uses_configured_host_alias() -> None:
    """Prometheus 抓取目标应使用已映射的宿主机别名。"""
    prometheus_config = _load_yaml(PROJECT_ROOT / "observability/prometheus/prometheus.yml")
    scrape_configs = prometheus_config["scrape_configs"]
    myapp_job = next(config for config in scrape_configs if config["job_name"] == "myapp")
    targets = myapp_job["static_configs"][0]["targets"]

    assert "host.docker.internal:8000" in targets
