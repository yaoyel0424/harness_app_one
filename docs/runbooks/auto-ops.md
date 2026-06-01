# 自动运维 Runbook

本文说明 **自动跟踪日志 → 自动修复 → 自动提交 → 自动扩容** 的完整链路。

## 架构

```
myapp (/metrics + JSON 日志)
    ↓
Prometheus 告警 / Grafana Loki 告警
    ↓
Alertmanager / Grafana Contact Point
    ↓
oncall-relay (scripts/oncall_relay.py)
    ↓
GitHub repository_dispatch
    ↓
.github/workflows/oncall-dispatch.yml
    ↓
scripts/ai_oncall.py (Cursor Cloud Agent)
    ↓
自动 PR → CI → (可选) auto-merge.yml
```

K8s 环境：`deploy/k8s/deployment-hpa.yaml` 中 HPA 根据 CPU/内存自动扩容 Pod。

## 一、前置配置

### 1. GitHub Secrets

| Secret | 说明 |
|--------|------|
| `CURSOR_API_KEY` | [Cursor Dashboard → Integrations](https://cursor.com/dashboard/integrations) |
| `ONCALL_WEBHOOK_SECRET` | 随机字符串，与 relay 一致 |
| `GITHUB_TOKEN` | 默认 `GITHUB_TOKEN` 即可（workflow 权限） |

### 2. GitHub Variables

| Variable | 建议值 | 说明 |
|----------|--------|------|
| `AUTO_FIX_ENABLED` | `true` | 总开关 |
| `AUTO_MERGE_ENABLED` | `false` | 稳定后可改 `true` |

### 3. 本地 observability 环境

```powershell
copy .env.example .env
# 编辑 GITHUB_TOKEN、GITHUB_REPO、ONCALL_WEBHOOK_SECRET（见 .env 底部章节）

docker compose -f docker-compose.observability.yml --env-file .env up -d
```

### 4. 应用日志进入 Loki（可选）

在 `.env` 中设置：

```env
LOG_FILE=logs/myapp.jsonl
```

启动应用后 Promtail 会采集 `logs/*.jsonl`。

## 二、自动跟踪日志

### Prometheus 指标告警（已内置）

| 告警 | 触发条件 | 动作 |
|------|----------|------|
| `MyAppHighErrorRate` | 5xx > 5% | auto-fix |
| `MyAppDown` | /metrics 不可达 | auto-fix |
| `MyAppHighLatency` | P95 > 2s | scale-advisory |
| `MyAppHighQPS` | QPS > 100 | scale-advisory |

规则文件：`observability/prometheus/alerts.yml`

### Grafana Loki 日志告警（手动补充）

1. 打开 Grafana → Alerting → New alert rule
2. 数据源选 Loki，查询示例：

```logql
sum(count_over_time({job="myapp"} | json | level="ERROR" [5m])) >= 3
```

3. Contact point 选 **oncall-relay**（已 provisioning）
4. 告警会以 `log-alert` 事件触发 GitHub Actions

## 三、自动修复与自动提交

1. `oncall-relay` 收到 webhook → `repository_dispatch`
2. `oncall-dispatch.yml` 运行 `scripts/ai_oncall.py`
3. Cursor Cloud Agent：
   - 读 `AGENTS.md`
   - 修复代码、跑测试
   - 开 PR，标签 `auto-fix`
4. 现有 `ci.yml` 自动验证 PR
5. `ci-auto-fix.yml`：主分支 CI 失败时也会触发修复

### 无 CURSOR_API_KEY 时

降级为 `gh issue create`，标签 `auto-fix`。

## 四、自动合并（L2）

启用仓库变量 `AUTO_MERGE_ENABLED=true` 后：

- PR 带 `auto-fix` 标签
- CI 全绿
- 变更文件在 `.github/auto-fix-allowlist.txt` 内

→ `auto-merge.yml` 自动 squash merge。

**默认关闭**，建议观察 2 周后再开。

## 五、自动扩容

### Docker / 本地

Compose 不支持 HPA。高 QPS/延迟告警触发 `scale-advisory`，AI 分析后可能：

- 调整 `deploy/k8s/deployment-hpa.yaml`
- 或修复 DB/代码瓶颈（不应盲目扩容）

### Kubernetes

```bash
kubectl apply -f deploy/k8s/deployment-hpa.yaml
```

HPA 配置：

- `minReplicas: 2`
- `maxReplicas: 10`
- CPU 目标 70%，内存 80%

AI 收到 `scale-advisory` 时会审查并 PR 调整 HPA 参数。

## 六、熔断与冷却

| 机制 | 配置 |
|------|------|
| relay 冷却 | `ONCALL_COOLDOWN_SEC=3600`（同类告警 1h 一次） |
| 总开关 | `ONCALL_ENABLED=false` 或 `AUTO_FIX_ENABLED=false` |
| allowlist | `.github/auto-fix-allowlist.txt` |

## 七、手动测试

```powershell
# 模拟 GitHub dispatch（需 gh CLI）
gh api repos/{owner}/{repo}/dispatches \
  -f event_type=metric-alert \
  -f "client_payload[webhook_secret]=YOUR_SECRET" \
  -f "client_payload[source]=manual-test"

# 或直接跑 workflow
gh workflow run oncall-dispatch.yml -f mode=metric-alert
```

## 八、Cursor Automation 配置

Cursor Automation 定义文件在 **`.cursor/automations/`**：

| 文件 | 用途 |
|------|------|
| `oncall-auto-fix.yaml` | Webhook → 自动修复并开 PR |
| `oncall-scale-advisory.yaml` | Webhook → 扩容/HPA 分析 |
| `ci-failure-auto-fix.yaml` | Git CI 失败 → 自动修复 |
| `README.md` | 安装步骤与三种接入方式 |

### 安装流程

1. Cursor → **Automations** → **New automation**
2. 对照 YAML 填写 Trigger / Tools（勾选 **Open or update PRs**）/ Instructions
3. 将 `YOUR_ORG/harness` 替换为实际仓库
4. 保存后复制 **Webhook URL** 到 `.env`：

```env
CURSOR_AUTOMATION_WEBHOOK_URL=https://api.cursor.com/automations/xxx/webhook
```

5. 重启 observability 栈，`oncall-relay` 会双路转发（GitHub + Cursor）

### 与 GitHub Actions 的关系

| 路径 | 配置 | 适用场景 |
|------|------|----------|
| **Cursor Automation** | `.cursor/automations/*.yaml` | 偏好 Cursor UI、无需 `CURSOR_API_KEY` |
| **GHA + SDK** | `.github/workflows/oncall-dispatch.yml` | 偏好 GitHub 日志、已有 Actions Secrets |

两条路径可**并存**（relay 双发）或**二选一**。Alertmanager 直连 Cursor 示例见 `observability/alertmanager/alertmanager-cursor.example.yml`。
