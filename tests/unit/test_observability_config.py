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
    """读取仓库内多文档 YAML 配置文件。"""
    content = (ROOT_DIR / relativePath).read_text(encoding="utf-8")
    documents = [doc for doc in yaml.safe_load_all(content) if doc is not None]
    assert all(isinstance(doc, dict) for doc in documents)
    return documents


def _find_k8s_document(kind: str) -> dict[str, Any]:
    """按 Kubernetes kind 查找部署清单。"""
    for document in _load_yaml_documents("deploy/k8s/deployment-hpa.yaml"):
        if document.get("kind") == kind:
            return document
    raise AssertionError(f"未找到 Kubernetes {kind} 配置")


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


def test_database_url_matches_compose_postgres_port() -> None:
    """默认数据库地址应匹配 Docker Compose 暴露的 5433 端口。"""
    compose_config = _load_yaml("docker-compose.yml")

    postgres_ports = compose_config["services"]["postgres"]["ports"]
    app_database_url = compose_config["services"]["app"]["environment"]["DATABASE_URL"]

    assert (
        Settings.model_fields["database_url"].default
        == "postgresql+asyncpg://myapp:myapp@127.0.0.1:5433/myapp"
    )
    assert "5433:5432" in postgres_ports
    assert app_database_url == "postgresql+asyncpg://myapp:myapp@postgres:5432/myapp"


def test_kubernetes_health_probes_are_explicitly_configured() -> None:
    """K8s 探针应使用独立健康端点并显式限制探测频率。"""
    deployment = _find_k8s_document("Deployment")
    container = deployment["spec"]["template"]["spec"]["containers"][0]

    liveness_probe = container["livenessProbe"]
    readiness_probe = container["readinessProbe"]

    assert liveness_probe["httpGet"]["path"] == "/health/live"
    assert readiness_probe["httpGet"]["path"] == "/health/ready"
    assert liveness_probe["periodSeconds"] >= 20
    assert readiness_probe["periodSeconds"] >= 10
    assert liveness_probe["timeoutSeconds"] == 2
    assert readiness_probe["timeoutSeconds"] == 2


def test_high_qps_scale_advisory_has_hpa_headroom() -> None:
    """MyAppHighQPS 告警触发后 HPA 应保留足够扩容上限。"""
    hpa = _find_k8s_document("HorizontalPodAutoscaler")
    hpa_spec = hpa["spec"]

    assert hpa_spec["minReplicas"] == 2
    assert hpa_spec["maxReplicas"] >= 20
