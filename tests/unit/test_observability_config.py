"""可观测性配置回归测试。"""

from pathlib import Path
from typing import Any

import yaml


ROOT_DIR = Path(__file__).resolve().parents[2]


def _load_yaml(relativePath: str) -> dict[str, Any]:
    """读取仓库内 YAML 配置文件。"""
    content = (ROOT_DIR / relativePath).read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert isinstance(data, dict)
    return data


def test_prometheus_host_internal_target_has_linux_host_gateway() -> None:
    """Prometheus 抓宿主机指标时应兼容 Linux Docker 的 host 网关别名。"""
    prometheus_config = _load_yaml("observability/prometheus/prometheus.yml")
    scrape_configs = prometheus_config["scrape_configs"]
    host_internal_targets = [
        target
        for scrape_config in scrape_configs
        for static_config in scrape_config.get("static_configs", [])
        for target in static_config.get("targets", [])
        if str(target).startswith("host.docker.internal:")
    ]

    compose_config = _load_yaml("docker-compose.observability.yml")
    prometheus_service = compose_config["services"]["prometheus"]

    assert host_internal_targets == ["host.docker.internal:8000"]
    assert "host.docker.internal:host-gateway" in prometheus_service.get("extra_hosts", [])
