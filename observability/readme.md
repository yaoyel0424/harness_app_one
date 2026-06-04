下面按 **「整体架构 → 两条告警链 → 各文件职责 → 它们怎么串起来」** 说明 `observability/` 目录。

---

## 一、总览：三块可观测 + 一条自动运维

```text
                    ┌─────────────────────────────────────────┐
                    │              myapp 应用                  │
                    │  /metrics  │  JSON 日志  │  OTLP(可选)  │
                    └─────┬──────────┬──────────────┬─────────┘
                          │          │              │
         指标链           │          │  日志链       │  追踪链
                          ▼          ▼              ▼
                    Prometheus   Promtail→Loki    Tempo
                          │          │              │
                          │     Grafana 查/告警      │
                          ▼          │              │
                    alerts.yml       │              │
                          │          ▼              │
                          ▼     rules.yaml          │
                    Alertmanager◄──(Loki ruler 可连，本项主要 Grafana 告警)
                          │
                          ▼
                    oncall-relay (:8787)
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
        GitHub dispatch          Cursor Webhook
        (GHA + ai_oncall)        (Automation)

Grafana (:3000)：统一看板
  - datasources.yml → 连 Prometheus / Loki / Tempo
  - 不负责 Prometheus 那条 metric 告警（那是 Prometheus→Alertmanager）
```

`**docker-compose.observability.yml**` 把上述服务放进同一 Docker 网络 `observability`，配置文件通过 volume 挂载进容器。

---

## 二、两条「会自动修代码」的告警链（并行）

### 链 A：Prometheus 指标告警


| 步骤   | 配置                                                           | 作用                                                                  |
| ---- | ------------------------------------------------------------ | ------------------------------------------------------------------- |
| 1 采集 | `prometheus/prometheus.yml`                                  | 每 15s 拉 `host.docker.internal:8000/metrics`，打 label `service=myapp` |
| 2 规则 | `prometheus/alerts.yml`                                      | 4 条 PromQL 告警（5xx、延迟、QPS、down）                                      |
| 3 评估 | `prometheus.yml` 的 `rule_files` + `evaluation_interval: 15s` | Prometheus 自己算规则                                                    |
| 4 通知 | `prometheus.yml` → `alertmanager:9093`                       | firing 告警交给 Alertmanager                                            |
| 5 路由 | `alertmanager/alertmanager.yml`                              | 分组、抑制、POST 到 relay                                                  |
| 6 转发 | `scripts/oncall_relay.py`（容器挂载）                              | → `repository_dispatch`（`metric-alert` / `scale-advisory`）          |


### 链 B：Loki 日志告警（Grafana 评估）


| 步骤    | 配置                                           | 作用                                    |
| ----- | -------------------------------------------- | ------------------------------------- |
| 1 写日志 | 应用 `LOG_FILE=logs/myapp.jsonl`（宿主机 `./logs`） | JSON 行日志                              |
| 2 采集  | `promtail/promtail.yml`                      | tail `./logs/*.jsonl`，推 Loki          |
| 3 存储  | `loki/loki.yaml` + volume `loki-data`        | 日志索引/块持久化                             |
| 4 规则  | `grafana/.../rules.yaml`                     | LogQL 查 Loki，Grafana Unified Alerting |
| 5 通知  | `grafana/.../contact-points.yaml`            | 按 alertname 选 receiver                |
| 6 转发  | 同链 A：`http://oncall-relay:8787/webhook`      | relay 识别为 Grafana 格式 → `log-alert`    |


**重要区别**：指标告警 **不经过 Grafana**；日志告警 **不经过 Prometheus**。两条最后在 **oncall-relay** 汇合。

---

## 三、各目录/文件详解

### 1. `prometheus/`

`**prometheus.yml`** — Prometheus 主配置

```1:22:d:\cursor\harness\observability\prometheus\prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093
rule_files:
  - /etc/prometheus/alerts.yml
scrape_configs:
  - job_name: myapp
    metrics_path: /metrics
    static_configs:
      - targets:
          - host.docker.internal:8000
        labels:
          service: myapp
```

- **scrape**：从宿主机 8000 抓应用指标；`docker-compose.observability.yml` 为 Prometheus 配置了 `host.docker.internal:host-gateway`，兼容 Linux Docker。
- **rule_files**：加载同目录 `alerts.yml`
- **alerting**：把告警发给 Alertmanager 容器

`**alerts.yml`** — 指标告警条件 + `**oncall_action` / `alert_type` 标签**（后面 relay 和 GHA 用）


| 告警                             | 动作 label                    |
| ------------------------------ | --------------------------- |
| MyAppHighErrorRate, MyAppDown  | `auto-fix` → `metric-alert` |
| MyAppHighLatency, MyAppHighQPS | `scale-advisory`            |


---

### 2. `alertmanager/`

`**alertmanager.yml`** — 告警「邮局」：合并、抑制、发 webhook


| 段落                               | 作用                                                               |
| -------------------------------- | ---------------------------------------------------------------- |
| `route`                          | 默认 receiver `oncall-relay`；按 `oncall_action` 分子路由（都指向同一 webhook） |
| `group_by`                       | 同 `alertname`+`service` 合并，减少轰炸                                  |
| `group_wait` / `repeat_interval` | 30s 聚合窗口；4h 重复通知间隔                                               |
| `receivers`                      | 真正 URL：`http://oncall-relay:8787/webhook`（Compose 服务名）           |
| `inhibit_rules`                  | `MyAppDown` firing 时抑制同 service 的 `MyAppHighErrorRate`           |


`**alertmanager-cursor.example.yml**` — 示例：绕过 relay，Alertmanager 直连 Cursor Webhook（可选，未默认启用）。

---

### 3. `promtail/` + `loki/`

`**promtail/promtail.yml**`

```11:20:d:\cursor\harness\observability\promtail\promtail.yml
scrape_configs:
  - job_name: myapp-file
    static_configs:
      - targets:
          - localhost
        labels:
          job: myapp
          service: myapp
          ingest: promtail
          __path__: /mnt/myapp-logs/*.jsonl
```

- 读容器内 `/mnt/myapp-logs` = 宿主机 `./logs`
- 推到 `http://loki:3100`
- 标签 `job=myapp`, `ingest=promtail` 供 Grafana LogQL 使用

`**loki/loki.yaml**`

- 单节点 Loki，数据在 volume `**loki-data:/loki**`（重启不丢）
- `ruler.alertmanager_url` 指向 Alertmanager（本项目的日志告警主要在 **Grafana rules.yaml**，不是 Loki ruler）

---

### 4. `grafana/provisioning/`

Grafana 启动时自动导入，无需手点 UI。

`**datasources/datasources.yml`** — 三个数据源 UID 与告警/Explore 对应：


| 名称         | URL                      | uid          |
| ---------- | ------------------------ | ------------ |
| Prometheus | `http://prometheus:9090` | `prometheus` |
| Loki       | `http://loki:3100`       | `loki`       |
| Tempo      | `http://tempo:3200`      | `tempo`      |


`**alerting/rules.yaml**` — 两条 **Loki 日志告警**：


| 规则                         | 条件                    | 联系                                                                   |
| -------------------------- | --------------------- | -------------------------------------------------------------------- |
| **MyAppErrorLogSpike**     | 5 分钟内 ERROR > 3，持续 5m | `oncall_action: auto-fix` → contact → **oncall-relay** → `log-alert` |
| **MyAppPromtailLogNotify** | 5 分钟内 ERROR ≥ 1，持续 2m | `notify_only` → **log-notify-only**（邮件，不 auto-fix）                   |


LogQL 示例：`{job="myapp", ingest="promtail"} | json | level="ERROR"`。

`**alerting/contact-points.yaml`** — 把规则接到谁：

```35:41:d:\cursor\harness\observability\grafana\provisioning\alerting\contact-points.yaml
    routes:
      - receiver: oncall-relay
        matchers:
          - alertname = MyAppErrorLogSpike
      - receiver: log-notify-only
        matchers:
          - alertname = MyAppPromtailLogNotify
```

与 Alertmanager 的 `receiver: oncall-relay` **同名不同系统**：都是 POST 同一个 relay URL。

---

### 5. `tempo/`

`**tempo.yaml`** — 接收 OTLP gRPC `:4317`，查询 HTTP `:3200`，本地存储约 **1h** 保留。

- **只用于追踪查询**（Grafana Explore → Tempo）
- **不参与** 当前 `alerts.yml` / Grafana 日志告警链
- 需应用 `OTEL_ENABLED=true` 才有数据

---

### 6. 文档

`**promtail-loki-grafana.md`** — Loki 链路的逐步说明（与上面链 B 一致），可作 runbook 补充。

---

## 四、汇合点：oncall-relay（不在 observability 目录，但被挂载）

Compose 把 `scripts/oncall_relay.py` 挂进 `**oncall-relay` 容器**，环境变量来自 `**.env`**：

- `GITHUB_TOKEN` / `GITHUB_REPO` → GitHub dispatch
- `CURSOR_AUTOMATION_WEBHOOK_*` → Cursor（可选）
- `ONCALL_COOLDOWN_SEC` → 按 alertname 冷却

relay 根据 HTTP body 格式分支：

- 有 `commonLabels` → Alertmanager（链 A）→ 读 `labels.oncall_action`
- 否则 → Grafana（链 B）→ 固定 `log-alert`（且只处理 `MyAppErrorLogSpike`）

---

## 五、配置之间的「引用关系」图

```text
prometheus.yml ──loads──► alerts.yml
        │
        └──alerting──► alertmanager.yml ──webhook──► oncall-relay
                              ▲
                              │ (Loki ruler 预留，主路径不用)
loki.yaml ──ruler URL─────────┘

promtail.yml ──push──► loki.yaml
                           ▲
datasources.yml ──uid:loki──┤
rules.yaml ──LogQL──────────┘
rules.yaml ──datasourceUid: loki
contact-points.yaml ──webhook──► oncall-relay (MyAppErrorLogSpike)

datasources.yml ──uid:prometheus──► Grafana 看指标（不评估 metric 告警）
datasources.yml ──uid:tempo──► Grafana 看 trace

docker-compose.observability.yml
  挂载上述所有 yml + 挂 oncall_relay.py + volumes(loki-data, promtail-data, oncall-state)
```

---

## 六、和应用侧的配合（在 observability 外，但必须有）


| 能力     | 应用 / 宿主机                      | observability 哪用到       |
| ------ | ----------------------------- | ----------------------- |
| 指标     | 暴露 `/metrics`，监听 `:8000`      | `prometheus.yml` scrape |
| 日志     | `LOG_FILE` → `./logs/*.jsonl` | `promtail` 挂载 `./logs`  |
| 追踪     | `OTEL_ENABLED` + `:4317`      | `tempo.yaml`            |
| 自动修复凭证 | `.env`                        | `oncall-relay` 容器 env   |


---

## 七、端口速查（本机访问）


| 服务           | 端口          | 配置目录                         |
| ------------ | ----------- | ---------------------------- |
| Grafana      | 3000        | `grafana/provisioning/`      |
| Prometheus   | 9090        | `prometheus/`                |
| Alertmanager | 9093        | `alertmanager/`              |
| Loki         | 3100        | `loki/`                      |
| Tempo        | 3200 / 4317 | `tempo/`                     |
| Oncall relay | 8787        | `../scripts/oncall_relay.py` |


---

## 八、一句话总结

- `**prometheus/` + `alertmanager/**` = **指标异常 → relay → 自动运维**
- `**promtail/` + `loki/` + `grafana/alerting/`** = **日志异常 → Grafana 告警 → relay（或仅邮件）**
- `**grafana/datasources/`** = 把三类数据接到 Grafana UI
- `**tempo/**` = 分布式追踪，独立查询，默认不进告警
- `**oncall-relay**` = 两条告警链的 **唯一自动修复出口**（再加 GitHub Actions / Cursor）

若你想深入某一条（例如只画 `MyAppErrorLogSpike` 从 LogQL 到 PR 的逐步 JSON），可以指定规则名我按事件顺序展开。







**不是 Alertmanager 去拉。** 是 **Prometheus 自己采集、自己算规则，再把「告警结果」推送给 Alertmanager**。

---

## 分工

| 组件 | 做什么 | 数据从哪来 |
|------|--------|------------|
| **Prometheus** | 拉指标 + 存 TSDB + **评估 `alerts.yml`** | 主动 **scrape** 应用的 `/metrics` |
| **Alertmanager** | 收告警、分组、抑制、发 webhook | **不拉指标**，只 **收 Prometheus 发来的告警** |

Alertmanager **不会**访问 Prometheus 的 `/metrics`，也 **不会**跑 PromQL。

---

## 完整流程

```text
① 采集（Pull）
   prometheus.yml scrape_configs
   每 15s GET http://host.docker.internal:8000/metrics
   （Prometheus 容器通过 host-gateway 映射解析 host.docker.internal）
        ↓
   写入 Prometheus 本地 TSDB

② 评估（Prometheus 内部）
   rule_files → alerts.yml
   每 evaluation_interval（15s）对 TSDB 跑 PromQL
        ↓
   条件满足且 for 时间到 → 告警状态 firing

③ 上报告警（Push，不是 Alertmanager 拉）
   prometheus.yml 里：
   alerting:
     alertmanagers:
       - targets: [alertmanager:9093]
        ↓
   Prometheus 用 HTTP 把 firing/resolved 告警 POST 给 Alertmanager

④ Alertmanager 处理
   alertmanager.yml → 路由 → POST http://oncall-relay:8787/webhook
```

对应配置：

```5:10:d:\cursor\harness\observability\prometheus\prometheus.yml
alerting:
  alertmanagers:
    - static_configs:
        - targets:
            - alertmanager:9093
```

```12:13:d:\cursor\harness\observability\prometheus\prometheus.yml
rule_files:
  - /etc/prometheus/alerts.yml
```

---

## 两个「15 秒」别混

| 配置 | 含义 |
|------|------|
| `scrape_interval: 15s` | 每 15s **抓一次** `/metrics` |
| `evaluation_interval: 15s` | 每 15s **算一次** `alerts.yml` 里的规则 |

评估用的是 **已经抓进 TSDB 的指标**，不是 Alertmanager 去拉。

---

## 和 Grafana Loki 告警对比

| | Prometheus 链 | Loki 链 |
|--|---------------|---------|
| 谁评估 | **Prometheus** | **Grafana**（查 Loki） |
| 谁通知 | **Alertmanager** ← Prometheus 推送 | **Grafana** 直接 webhook → relay |
| Alertmanager 角色 | 收 metric 告警 | Loki 日志告警 **一般不经过** 这条（除非走 Loki ruler） |

---

## 如何自己验证

1. **Prometheus** http://localhost:9090/alerts — 看规则是否 Pending/Firing
2. **Alertmanager** http://localhost:9093 — 看是否收到同一批告警
3. 若 Prometheus 有 firing 而 Alertmanager 没有 → 查 `alerting.alertmanagers` 目标、网络是否通

**一句话**：`observability/prometheus/` 负责 **抓数 + 算规则**；算出来的告警由 **Prometheus 推给 Alertmanager**，不是 Alertmanager 来拉。
