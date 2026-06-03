下面按**配置文件 → 运行链路 → 两条告警规则 → 自动修复**说明 Loki 这一路（与 Prometheus 指标链并行）。

---

## 一、整体架构（Loki 链不负责采集，只存日志）

```text
myapp 写 JSON 日志
    ↓
Promtail tail 文件 → push
    ↓
Loki 存储
    ↓
Grafana Unified Alerting（LogQL 查 Loki）
    ↓
Contact Point（webhook / 邮件）
    ↓
oncall-relay（仅 auto-fix 规则）→ GitHub log-alert → ai_oncall.py
```

**Loki 本身不配告警**；告警在 **Grafana** 里配，数据来自 Loki。

---

## 二、第 1 步：应用产出日志

**文件**：`docker-compose.yml`（app 服务）

```yaml
LOG_FILE: /var/log/myapp/myapp.jsonl
volumes:
  - ./logs:/var/log/myapp
```

**代码**：`src/myapp/utils/logging.py` 写 JSONL；`src/myapp/api/handlers/exception_handlers.py`：

- 4xx/422 → `WARNING`（带 `status_code`）
- 未捕获异常 → **`ERROR`**（会进 Loki 告警统计）

要触发 ERROR 告警，需有未处理 500 或 `logger.error`。

---

## 三、第 2 步：Promtail 采集 → Loki

### Docker：`docker-compose.observability.yml`

```yaml
promtail:
  volumes:
    - ./observability/promtail/promtail.yml:/etc/promtail/config.yml:ro
    - ./logs:/mnt/myapp-logs:ro
  depends_on: [loki]

loki:
  image: grafana/loki:3.2.0
  ports: ["3100:3100"]
```

### 配置：`observability/promtail/promtail.yml`

| 项 | 值 | 含义 |
|----|-----|------|
| `clients.url` | `http://loki:3100/loki/api/v1/push` | 推到 Loki |
| `__path__` | `/mnt/myapp-logs/*.jsonl` | 对应宿主机 `./logs/*.jsonl` |
| 标签 | `job=myapp`, `ingest=promtail`, `service=myapp` | LogQL 筛选用 |

---

## 四、第 3 步：Grafana 数据源

**文件**：`observability/grafana/provisioning/datasources/datasources.yml`

```yaml
- name: Loki
  type: loki
  uid: loki          # 告警 rules 里 datasourceUid: loki
  url: http://loki:3100
```

**Docker**：Grafana 挂载 `./observability/grafana/provisioning`，并 `GF_UNIFIED_ALERTING_ENABLED: "true"`。

---

## 五、第 4 步：告警规则（核心）

**文件**：`observability/grafana/provisioning/alerting/rules.yaml`
分组：`myapp-log-alerts`，评估间隔 **1 分钟**。

### 规则 1：`MyAppErrorLogSpike` → **自动修复**

| 配置项 | 值 |
|--------|-----|
| LogQL | `sum(count_over_time({job="myapp", ingest="promtail"} \| json \| level="ERROR" [5m]))` |
| 阈值 | **> 3**（5 分钟内 ERROR 超过 3 条） |
| `for` | **5m**（条件持续 5 分钟才 firing） |
| `isPaused` | `false` |
| 标签 | `oncall_action: auto-fix`, `alert_channel: loki` |

### 规则 2：`MyAppPromtailLogNotify` → **仅通知**

| 配置项 | 值 |
|--------|-----|
| LogQL | 同上 |
| 阈值 | **> 0**（≥1 条 ERROR） |
| `for` | **2m** |
| 标签 | `notify_only: "true"`, `alert_channel: promtail` |

两条规则查**同一条 Loki 流**；ERROR ≥4 时可能**同时 firing**（通知 + auto-fix）。

---

## 六、第 5 步：Contact Point 与路由

**文件**：`observability/grafana/provisioning/alerting/contact-points.yaml`

### Contact Points

| 名称 | 类型 | URL/地址 | 用途 |
|------|------|----------|------|
| `oncall-relay` | webhook | `http://oncall-relay:8787/webhook` | auto-fix |
| `log-notify-only` | email | `ops@example.com` | 仅通知（需 SMTP） |

### Notification policies（按 alertname 路由）

```yaml
routes:
  - receiver: oncall-relay
    matchers: [alertname = MyAppErrorLogSpike]
  - receiver: log-notify-only
    matchers: [alertname = MyAppPromtailLogNotify]
```

**注意**：`MyAppPromtailLogNotify` **不应**指到 `oncall-relay`（即使误指，relay 也会忽略，见下节）。

邮件要生效需在 `docker-compose.observability.yml` 里取消注释 `GF_SMTP_*` 并填真实 SMTP。

---

## 七、第 6 步：oncall-relay → GitHub 自动修复

### Docker：`docker-compose.observability.yml` → `oncall-relay`

```yaml
environment:
  GITHUB_TOKEN: ${GITHUB_TOKEN}
  GITHUB_REPO: ${GITHUB_REPO}
  ONCALL_WEBHOOK_SECRET: ${ONCALL_WEBHOOK_SECRET}
  LOG_ALERT_AUTO_FIX_ENABLED: ${LOG_ALERT_AUTO_FIX_ENABLED:-true}
  ONCALL_COOLDOWN_SEC: ${ONCALL_COOLDOWN_SEC:-3600}
  CURSOR_AUTOMATION_WEBHOOK_URL: ...  # 可选
```

### 逻辑：`scripts/oncall_relay.py`

Grafana webhook → 识别为 **`log-alert`**（无 `commonLabels` 的 Alertmanager 格式）。

对 `log-alert` 的处理：

1. 仅 **`MyAppErrorLogSpike`** 允许继续（`AUTO_FIX_LOG_ALERT_NAMES`）
2. `LOG_ALERT_AUTO_FIX_ENABLED=true`（默认）
3. 冷却键 = `title`（如 `MyAppErrorLogSpike`），默认 **1h** 内不重复 dispatch
4. `POST https://api.github.com/repos/{GITHUB_REPO}/dispatches`
   - `event_type`: **`log-alert`**
5. 可选：再 POST Cursor Automation Webhook

`MyAppPromtailLogNotify` 若误进 relay → 返回 `ignored`，**不 dispatch**。

---

## 八、第 7 步：GitHub Actions → AI 修复

**文件**：`.github/workflows/oncall-dispatch.yml`

```yaml
on:
  repository_dispatch:
    types: [log-alert, metric-alert, scale-advisory]
if: vars.AUTO_FIX_ENABLED != 'false'
```

触发后运行 `scripts/ai_oncall.py --mode log-alert`，与 `metric-alert` 共用修复逻辑。

**GitHub 侧还需**：

- Secrets：`ONCALL_WEBHOOK_SECRET`、`CURSOR_API_KEY`
- Variables：`AUTO_FIX_ENABLED=true`

---

## 九、完整 auto-fix 链路（Loki 路）

```text
ERROR 日志写入 logs/myapp.jsonl
  → Promtail → Loki
  → Grafana 每 1m 评估 MyAppErrorLogSpike
  → 5m 内 ERROR>3 且持续 for 5m → Firing
  → Contact Point oncall-relay
  → POST oncall-relay:8787/webhook
  → repository_dispatch event_type=log-alert
  → oncall-dispatch.yml
  → ai_oncall.py 开 PR（auto-fix）
```

**仅通知链**（不修复）：

```text
ERROR ≥1 且 for 2m → MyAppPromtailLogNotify
  → log-notify-only（邮件，需 SMTP）
  → 不经过 GitHub auto-fix
```

---

## 十、与 Prometheus 链对比

| | Prometheus 链 | Loki 链 |
|--|---------------|---------|
| 数据 | `/metrics` 指标 | JSON 日志 |
| 评估 | Prometheus + `alerts.yml` | Grafana + LogQL |
| 通知入口 | **Alertmanager** :9093 | **Grafana** Contact Point |
| relay event | `metric-alert` | `log-alert` |
| 典型告警 | `MyAppHighErrorRate`（5xx 率） | `MyAppErrorLogSpike`（ERROR 条数） |

两路 **共用同一个 oncall-relay**，但 **冷却按 alertname 分开**（可能并行两次 auto-fix）。

---

## 十一、本地验证清单

1. `./logs/myapp.jsonl` 有 `"level": "ERROR"` 行
2. Grafana → Explore → Loki：
   `{job="myapp", ingest="promtail"} | json | level="ERROR"`
3. Grafana → Alerting → `MyAppErrorLogSpike` 状态
4. relay 日志：`GitHub dispatch 成功: log-alert 204`
5. GitHub → Actions → **Oncall Dispatch** 有 run

手动演练：

```powershell
gh workflow run oncall-dispatch.yml -f mode=log-alert
```

---

## 十二、相关文件索引

| 文件 | 作用 |
|------|------|
| `observability/promtail/promtail.yml` | 采集 |
| `observability/grafana/provisioning/datasources/datasources.yml` | Loki 数据源 |
| `observability/grafana/provisioning/alerting/rules.yaml` | 两条 Log 告警规则 |
| `observability/grafana/provisioning/alerting/contact-points.yaml` | webhook/邮件路由 |
| `scripts/oncall_relay.py` | log-alert → GitHub |
| `.github/workflows/oncall-dispatch.yml` | CI 自动修复 |
| `docs/runbooks/auto-ops.md` | Runbook 摘要 |
| `.env.example` | `LOG_ALERT_AUTO_FIX_ENABLED` 等 |

更细的 Runbook 见 `docs/runbooks/auto-ops.md` 第二节「Grafana Loki 日志告警」。
