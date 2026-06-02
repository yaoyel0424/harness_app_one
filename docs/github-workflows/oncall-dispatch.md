# oncall-dispatch.yml — 告警 AI 值班

> 对应文件：[`.github/workflows/oncall-dispatch.yml`](../../.github/workflows/oncall-dispatch.yml)

## 作用

接收 **Prometheus/Grafana 等运维告警**（经 `scripts/oncall_relay.py` 转发），或 **人工手动触发**，运行 `scripts/ai_oncall.py` 执行自动修复或扩容分析，最终由 Cursor Cloud Agent 开 PR。

这是自动运维链路中 **「告警 → GitHub Actions → AI」** 的 GitHub 侧入口。

## 何时执行

### 方式 A：repository_dispatch（生产路径）

```yaml
on:
  repository_dispatch:
    types:
      - log-alert      # Grafana Loki 等日志告警
      - metric-alert   # Prometheus 指标告警（如错误率、服务宕机）
      - scale-advisory # 高延迟/QPS，偏扩容分析
```

由 `oncall-relay` 调用 GitHub API：

```
POST /repos/{owner}/{repo}/dispatches
event_type: metric-alert | log-alert | scale-advisory
client_payload: { webhook_secret, alerts, ... }
```

### 方式 B：workflow_dispatch（调试/演练）

在 GitHub Actions UI 选择 **Oncall Dispatch → Run workflow**，指定 `mode`：

- `log-alert`
- `metric-alert`（默认）
- `scale-advisory`

手动模式会写入占位 payload：`{"source":"manual","message":"workflow_dispatch"}`。

### 全局条件

```yaml
if: vars.AUTO_FIX_ENABLED != 'false'
```

与 `ci-auto-fix.yml` 共用 `AUTO_FIX_ENABLED` 开关。

### 并发

```yaml
concurrency:
  group: oncall-${{ github.event.action || github.event.inputs.mode }}
  cancel-in-progress: false
```

同类型告警**不取消**进行中的 run，避免丢告警；不同类型（如 metric vs scale）可并行。

## Job：oncall — 步骤详解

### 1. 校验 Webhook 密钥

仅 `repository_dispatch` 时执行：

- 比较 `secrets.ONCALL_WEBHOOK_SECRET` 与 `client_payload.webhook_secret`
- Secret 已配置但不匹配 → **失败退出**，防止伪造 dispatch

若 Secret 未配置（空），则跳过校验（便于本地测试，生产应配置）。

### 2. Checkout + 安装依赖

标准 checkout；`pip install poetry` + `poetry install --with dev`。

### 3. 写入告警 payload

| 触发方式 | payload 来源 | `mode` 环境变量 |
|----------|--------------|-----------------|
| `repository_dispatch` | `toJson(github.event.client_payload)` | `github.event.action` |
| `workflow_dispatch` | 手动占位 JSON | `github.event.inputs.mode` |

输出文件：`alert-payload.json`

### 4. 运行 AI 值班

```bash
poetry run python scripts/ai_oncall.py \
  --mode "$mode" \
  --payload-file alert-payload.json
```

**mode 与 Prompt 行为：**

| mode | ai_oncall 行为 |
|------|----------------|
| `auto-fix` | 根因分析 + 代码修复 + PR（metric/log 告警默认走修复 Prompt） |
| `log-alert` | 同上（修复 Prompt） |
| `metric-alert` | 同上 |
| `scale-advisory` | 扩容/HPA 分析 Prompt，可能改 `deploy/k8s/deployment-hpa.yaml` |

**Secrets：**

| 名称 | 说明 |
|------|------|
| `CURSOR_API_KEY` | 必需（否则降级开 Issue） |
| `GITHUB_TOKEN` | PR/Issue 操作 |

## 完整告警链路

```
myapp /metrics + JSON 日志
    ↓
Prometheus alerts.yml / Grafana Loki
    ↓
Alertmanager / Grafana Contact Point
    ↓
scripts/oncall_relay.py (:8787)
    ├─ dispatch_github() → repository_dispatch → 本 Workflow
    └─ dispatch_cursor_automation() → Cursor Webhook（可选，见 .cursor/automations/）
    ↓
scripts/ai_oncall.py
    ↓
Cursor Cloud Agent → PR (标签 auto-fix)
    ↓
ci.yml → auto-merge.yml（可选）
```

## 与 Cursor Automation 的关系

| 路径 | 配置位置 | 特点 |
|------|----------|------|
| **本 Workflow** | `.github/workflows/oncall-dispatch.yml` | 日志在 GitHub Actions；需 `CURSOR_API_KEY` |
| **Cursor Automation** | `.cursor/automations/oncall-*.yaml` | Webhook 触发；Cursor UI 配置；无需 API Key |

`oncall-relay` 可同时双发；Alertmanager 也可直连 Cursor Webhook（见 `observability/alertmanager/alertmanager-cursor.example.yml`）。

## 手动演练

```bash
# GitHub CLI
gh workflow run oncall-dispatch.yml -f mode=metric-alert

# 或模拟 dispatch
gh api repos/{owner}/{repo}/dispatches \
  -f event_type=metric-alert \
  -f "client_payload[webhook_secret]=YOUR_SECRET"
```

## 注意事项

- relay 内置**冷却**（同 alertname 重复告警可能跳过）；本 Workflow 无二次冷却。
- `scale-advisory` 与 `metric-alert` 在 Prometheus 规则中通过 `oncall_action` label 区分（见 `observability/prometheus/alerts.yml`）。
- 详细 Runbook：[docs/runbooks/auto-ops.md](../runbooks/auto-ops.md)
