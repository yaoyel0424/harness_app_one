"""Kubernetes HPA 清单测试。"""

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
HPA_PATH = REPO_ROOT / "deploy" / "k8s" / "deployment-hpa.yaml"


def _load_hpa_manifest() -> dict[str, Any]:
    """读取 myapp 的 HPA 清单。"""
    documents = list(yaml.safe_load_all(HPA_PATH.read_text(encoding="utf-8")))
    hpa_manifest = next(
        (
            document
            for document in documents
            if isinstance(document, dict) and document.get("kind") == "HorizontalPodAutoscaler"
        ),
        None,
    )
    assert hpa_manifest is not None
    return hpa_manifest


def test_hpa_allows_headroom_for_high_qps_advisory() -> None:
    """高 QPS 告警触发后 HPA 应保留足够扩容上限。"""
    spec = _load_hpa_manifest()["spec"]

    assert spec["minReplicas"] == 2
    assert spec["maxReplicas"] >= 20


def test_hpa_scales_up_aggressively_for_sustained_qps() -> None:
    """持续高 QPS 时 HPA 应优先采用更快的扩容策略。"""
    scale_up = _load_hpa_manifest()["spec"]["behavior"]["scaleUp"]
    policies = {policy["type"]: policy for policy in scale_up["policies"]}

    assert scale_up["stabilizationWindowSeconds"] <= 30
    assert scale_up["selectPolicy"] == "Max"
    assert policies["Percent"]["value"] >= 200
    assert policies["Pods"]["value"] >= 4
