"""可观测性配置回归测试。"""

from pathlib import Path
from typing import Any

import yaml

from myapp.config import Settings

ROOT_DIR = Path(__file__).resolve().parents[2]


def _load_yaml(relativePath: str) -> dict[str, Any]:
    """读取仓库内 YAML 配置文件。"""
    content = (ROOT_DIR / relativePath).read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert isinstance(data, dict)
    return data


def _load_yaml_documents(relativePath: str) -> list[dict[str, Any]]:
    """读取包含多个 YAML 文档的配置文件。"""
    content = (ROOT_DIR / relativePath).read_text(encoding="utf-8")
    documents: list[dict[str, Any]] = []
    for document in yaml.safe_load_all(content):
        if document is None:
            continue
        assert isinstance(document, dict)
        documents.append(document)
    return documents


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


def test_database_url_matches_compose_postgres_host_port() -> None:
    """默认数据库连接串应对齐 Compose 暴露的宿主机 5433 端口。"""
    compose_config = _load_yaml("docker-compose.yml")
    postgres_service = compose_config["services"]["postgres"]

    assert "5433:5432" in postgres_service["ports"]
    assert (
        Settings.model_fields["database_url"].default
        == "postgresql+asyncpg://myapp:myapp@127.0.0.1:5433/myapp"
    )


def test_hpa_has_capacity_for_high_qps_scale_advisory() -> None:
    """高 QPS 告警对应的 HPA 应保留足够扩容上限并使用健康探针。"""
    documents = _load_yaml_documents("deploy/k8s/deployment-hpa.yaml")
    deployment = next(document for document in documents if document.get("kind") == "Deployment")
    hpa = next(
        document for document in documents if document.get("kind") == "HorizontalPodAutoscaler"
    )

    container = deployment["spec"]["template"]["spec"]["containers"][0]
    assert container["livenessProbe"]["httpGet"]["path"] == "/health/live"
    assert container["readinessProbe"]["httpGet"]["path"] == "/health/ready"

    hpa_spec = hpa["spec"]
    assert hpa_spec["minReplicas"] == 2
    assert hpa_spec["maxReplicas"] == 20
