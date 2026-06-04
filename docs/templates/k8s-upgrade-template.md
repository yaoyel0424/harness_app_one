# K8s 升级方案模板

> 从 Docker Compose / 本地开发迁移到 Kubernetes 时使用。复制本模板为 `docs/adr/NNNN-k8s-upgrade.md` 或团队 Wiki 页面，逐项填写后评审。

## 元信息

| 字段 | 内容 |
|------|------|
| 方案编号 | <!-- 如 UPGRADE-2026-001 --> |
| 状态 | 草案 / 评审中 / 已批准 / 执行中 / 已完成 |
| 负责人 | <!-- SRE / 平台 / 后端 --> |
| 目标环境 | <!-- 如 staging / production --> |
| 计划窗口 | <!-- YYYY-MM-DD HH:MM ~ HH:MM --> |
| 关联 ADR | <!-- 如有架构决策记录，填链接 --> |

## 1. 背景与目标

### 1.1 现状

<!-- 描述当前部署方式，例如： -->

- 应用：`docker-compose.yml`（app + postgres + docs）
- 可观测性：`docker-compose.observability.yml`（Prometheus、Loki、Promtail、Grafana、Tempo、Alertmanager、oncall-relay）
- 本地开发：`poetry run myapp`，端口 **8000**；文档站 **8001**
- K8s 清单：仓库已有 `deploy/k8s/deployment-hpa.yaml`（**仅 myapp + HPA，尚未 apply 则不生效**）

### 1.2 升级目标

<!-- 勾选或补充 -->

- [ ] 业务应用（myapp）上 K8s，支持 HPA 自动扩缩容
- [ ] 文档站（docs）独立 Pod 部署
- [ ] PostgreSQL：<!-- 托管 RDS / K8s StatefulSet / 保持 Compose 外置 -->
- [ ] 可观测性栈：<!-- 迁入 K8s / 独立 observability 集群 / 使用托管 Grafana Cloud -->
- [ ] 保留现有告警 → relay → GitHub/Cursor 自动运维链路
- [ ] CI 构建镜像并自动部署到集群

### 1.3 非目标（明确不做）

-

## 2. 服务映射与 Workload 选型

将 Compose 服务映射为 K8s 资源。**HPA 仅适用于无状态、可水平扩展的 Deployment**。

| Compose 服务 | K8s Namespace | Workload 类型 | 副本策略 | HPA | 备注 |
|--------------|---------------|-----------------|----------|-----|------|
| app (myapp) | `app` | Deployment | min <!-- --> / max <!-- --> | ✅ CPU/内存 <!-- 可选 QPS 自定义指标 --> | 已有 `deploy/k8s/deployment-hpa.yaml` |
| docs | `app` | Deployment | 固定 1～2 | ⚠️ 通常不需要 | `Dockerfile.docs` + Nginx :8001 |
| postgres | `data` | StatefulSet 或 **云 RDS** | 1（主） | ❌ | 生产推荐托管库 |
| prometheus | `observability` | StatefulSet / Helm | <!-- --> | ⚠️ 一般固定 | 需改 scrape 目标，弃用 `host.docker.internal` |
| alertmanager | `observability` | StatefulSet | 1～3 | ❌ | webhook 指向集群内 relay |
| loki | `observability` | StatefulSet + PVC | <!-- --> | ⚠️ | 需持久卷 |
| promtail | `observability` | **DaemonSet** | 每节点 1 | ❌ | 改采 K8s Pod 日志，非宿主机 `./logs` |
| tempo | `observability` | Deployment | <!-- --> | ⚠️ | myapp `OTEL_EXPORTER_ENDPOINT` 指向集群内 Service |
| grafana | `observability` | Deployment | 1～2 | ⚠️ | Ingress 对外 |
| oncall-relay | `observability` | Deployment | 1～2 | ❌ | Secret 注入 GitHub/Cursor 变量 |

## 3. 集群前置条件

迁移前确认集群已具备：

| 组件 | 是否就绪 | 说明 |
|------|----------|------|
| metrics-server | ☐ | HPA 按 CPU/内存扩缩 **必需** |
| Ingress Controller | ☐ | 对外暴露 API / Grafana / 文档 |
| StorageClass | ☐ | Loki、Postgres（若自建）等 PVC |
| 镜像仓库 | ☐ | 替换 YAML 中 `myapp:latest` |
| ExternalDNS / 证书 | ☐ | 可选，HTTPS 与域名 |
| Prometheus Adapter | ☐ | 可选，HPA 按 QPS 扩缩（对齐 `MyAppHighQPS` 告警） |

验证命令：

```bash
kubectl top nodes          # metrics-server 正常时应返回数据
kubectl get storageclass
kubectl get ingressclass
```

## 4. 配置与密钥迁移

### 4.1 Secret 清单

| Secret 名称 | 键 | 来源（.env / 云密钥） |
|-------------|-----|----------------------|
| `myapp-secrets` | `database-url` | `DATABASE_URL` |
| `myapp-secrets` | <!-- 其他 --> | <!-- --> |
| `oncall-relay-secrets` | `github-token` | `GITHUB_TOKEN` |
| `grafana-secrets` | `admin-password` | <!-- --> |

创建示例：

```bash
kubectl create namespace app
kubectl create secret generic myapp-secrets -n app \
  --from-literal=database-url='postgresql+asyncpg://user:pass@host:5432/myapp'
```

### 4.2 ConfigMap / 配置改造要点

| 配置项 | Compose 现状 | K8s 目标 |
|--------|--------------|----------|
| Prometheus scrape | `host.docker.internal:8000` | ServiceMonitor 或 `myapp.app.svc:80/metrics` |
| 应用日志 | `LOG_FILE` 写宿主机 `./logs` | stdout JSON 或 Promtail DaemonSet 采 Pod 日志 |
| OTEL | `host.docker.internal:4317` | `tempo.observability.svc:4317` |
| Alertmanager webhook | `host.docker.internal:8787` | `oncall-relay.observability.svc:8787` |

## 5. 分阶段 rollout 计划

建议分阶段降低风险，每阶段有可独立回滚的验收标准。

### 阶段 0：准备（D-7 ~ D-1）

- [ ] 评审本方案
- [ ] 构建并推送镜像：`myapp`、`docs`
- [ ] 准备数据库（RDS 或迁移脚本）
- [ ] 在 staging 集群演练 `kubectl apply`

### 阶段 1：数据层

- [ ] 部署 / 接入 PostgreSQL
- [ ] 执行 `alembic upgrade head`
- [ ] 验证应用可连库

### 阶段 2：应用层（myapp）

- [ ] `kubectl apply -f deploy/k8s/deployment-hpa.yaml`（更新镜像地址与 namespace）
- [ ] 创建 Ingress / 切少量流量
- [ ] 验证 `/health/live`、`/health/ready`、`/metrics`
- [ ] 确认 HPA：`kubectl get hpa -n app`

### 阶段 3：文档站

- [ ] 部署 docs Deployment + Service + Ingress（:8001）
- [ ] 验证静态站点可访问

### 阶段 4：可观测性

- [ ] 部署 Prometheus / Loki / Tempo / Grafana / Alertmanager / oncall-relay
- [ ] Promtail DaemonSet 采集 Pod 日志
- [ ] 更新 `observability/prometheus/prometheus.yml` 或使用 Helm kube-prometheus-stack
- [ ] 验证 Grafana 数据源、告警规则、`scale-advisory` 链路

### 阶段 5：切流与下线 Compose

- [ ] DNS / Ingress 全量切到 K8s
- [ ] 观察 24～72h（错误率、P95、HPA 行为）
- [ ] 下线 Compose 栈（保留回滚窗口）

## 6. 扩缩容（HPA）策略

### 6.1 myapp（主战场）

参考仓库默认（`deploy/k8s/deployment-hpa.yaml`）：

| 参数 | 当前默认值 | 目标值（填写） |
|------|------------|----------------|
| minReplicas | 2 | |
| maxReplicas | 10 | |
| CPU 目标 | 70% | |
| memory 目标 | 80% | |
| scaleUp 稳定窗口 | 60s | |
| scaleDown 稳定窗口 | 300s | |

自定义指标（可选）：Prometheus Adapter 暴露 `http_requests_per_second`，与 `MyAppHighQPS` 告警对齐。

### 6.2 不宜 HPA 的组件

<!-- 说明 postgres、promtail、alertmanager 等为何固定副本或使用其他扩缩方式 -->

-

### 6.3 与自动运维联动

- Prometheus 告警 `MyAppHighLatency` / `MyAppHighQPS` → `oncall_action=scale-advisory`
- AI / 人工审查后修改 `deploy/k8s/deployment-hpa.yaml` 并 `kubectl apply`
- 详见 [自动运维 Runbook](../runbooks/auto-ops.md)

## 7. CI/CD 变更

| 步骤 | 现状 | 目标 |
|------|------|------|
| 镜像构建 | CI `docker` job，仅 build 不 push | push 到 `your-registry/myapp:${{ github.sha }}` |
| 部署 | 无 | `kubectl apply` / Helm / Argo CD |
| SBOM | Artifact 归档 | 可选接镜像扫描 |

<!-- 填写实际 pipeline 变更 PR 链接 -->

## 8. 回滚方案

| 触发条件 | 回滚动作 | 负责人 | RTO 目标 |
|----------|----------|--------|----------|
| 就绪探针大面积失败 | `kubectl rollout undo deployment/myapp` | | |
| 数据库迁移失败 | 停止切流，恢复 Compose / 旧库快照 | | |
| 观测栈不可用 | 业务不受影响则延后；否则回滚 observability 阶段 | | |

Compose 回滚（保留至稳定期结束）：

```powershell
docker compose -f docker-compose.yml up -d --build
```

## 9. 验收清单

### 9.1 功能

- [ ] API：`/docs`（Swagger）、业务接口正常
- [ ] 文档站：`http://<!-- ingress -->:8001` 可访问
- [ ] 数据库读写、Alembic 版本正确

### 9.2 可观测性

- [ ] Prometheus 能 scrape myapp `/metrics`
- [ ] Loki 能查到应用日志
- [ ] Tempo 能收到 trace（若开启 OTEL）
- [ ] Grafana 仪表盘与告警正常
- [ ] 测试告警 → oncall-relay → GitHub dispatch 成功

### 9.3 扩缩容

- [ ] `kubectl get hpa` 显示 TARGETS 非 `<unknown>`
- [ ] 压测后副本数在 min～max 范围内变化
- [ ] scaleDown 稳定窗口内无抖动

## 10. 风险与未决问题

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| metrics-server 未安装 | HPA 不工作 | 阶段 0 安装并验证 |
| Promtail 仍读宿主机路径 | Loki 无日志 | 改 DaemonSet + stdout 日志 |
| 双栈并行端口冲突 | 8000/8001 与 Compose 冲突 | 分环境或先停 Compose |

未决问题：

-

## 11. 参考

- [部署指南](../runbooks/deploy.md) — K8s 第三节
- [自动运维 Runbook](../runbooks/auto-ops.md) — HPA 与 scale-advisory
- 仓库清单：`deploy/k8s/deployment-hpa.yaml`
- Compose 对照：`docker-compose.yml`、`docker-compose.observability.yml`
- [ADR 模板](adr-template.md)
