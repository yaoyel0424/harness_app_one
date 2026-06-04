# 部署指南

本文说明 **myapp** 在本地开发、Docker Compose 与 Kubernetes 上的部署方式。

## 前置条件

| 场景 | 需要 |
|------|------|
| 本地开发 | Python 3.12、[Poetry](https://python-poetry.org/) |
| Docker 部署 | Docker Desktop 或 Docker Engine + Compose v2 |
| 集成测试 | Docker（testcontainers） |
| Kubernetes | `kubectl`、可访问的集群、镜像仓库 |

## 环境变量

复制 `.env.example` 为 `.env` 并按环境修改：

```powershell
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

| 变量 | 说明 |
|------|------|
| `DATABASE_URL` | 异步 PostgreSQL 连接串；Compose 中 Postgres 映射宿主机 **5433** |
| `APP_ENV` | `development` / `test` / `production` |
| `LOG_FILE` | 可选，如 `logs/myapp.jsonl`，供 Promtail 采集 |
| `OTEL_ENABLED` | `true` 时启用 OpenTelemetry（需 Tempo 可达） |
| `OTEL_EXPORTER_ENDPOINT` | 默认 `http://localhost:4317` |
| `GITHUB_TOKEN` / `GITHUB_REPO` | 可观测性栈中 `oncall-relay` 使用（见 `.env.example` 底部） |
| `ONCALL_WEBHOOK_SECRET` | 告警 webhook 校验密钥 |

完整说明见仓库根目录 `.env.example`。

---

## 一、本地开发（Poetry）

适用于日常改代码、跑测试。

### 1. 安装依赖

```powershell
poetry install --with dev
poetry run pre-commit install   # 可选
```

Windows 无 `make` 时可直接用 `poetry run`；有 `make` 时可用 `make install`、`make run`。

### 2. 启动 PostgreSQL

应用启动时会连接数据库；非 `production` 环境会自动 `create_all` 建表。

```powershell
docker compose up -d postgres
```

默认连接串（`.env.example`）：

```text
postgresql+asyncpg://myapp:myapp@127.0.0.1:5433/myapp
```

### 3. 启动 API

```powershell
poetry run myapp
# 或: make run
```

### 4. 验证

| 端点 | 地址 |
|------|------|
| Swagger | http://127.0.0.1:8000/docs |
| 存活探针 | http://127.0.0.1:8000/health/live |
| 就绪探针 | http://127.0.0.1:8000/health/ready |
| Prometheus 指标 | http://127.0.0.1:8000/metrics |

### 5. 数据库迁移（共享库 / 生产）

开发环境可用自动建表；**正式 PostgreSQL** 应使用 Alembic：

```powershell
poetry run alembic upgrade head
```

迁移脚本位于 `alembic/versions/`。详见 Alembic 注释与 `alembic/env.py`。

---

## 二、Docker Compose

项目有两个 Compose 文件：

| 文件 | 内容 |
|------|------|
| `docker-compose.yml` | **app** + **postgres** |
| `docker-compose.observability.yml` | Prometheus、Loki、Promtail、Grafana、Tempo、Alertmanager、oncall-relay |

两套栈使用**不同 Docker 网络**（`app-net` / `observability`），合并启动时通过宿主机端口互通。

### 2.1 仅应用 + PostgreSQL

```powershell
docker compose up -d --build
```

| 服务 | 说明 |
|------|------|
| app | http://127.0.0.1:8000 |
| postgres | 宿主机 `5433` → 容器 `5432`，用户/库均为 `myapp` |

停止：`docker compose down`

### 2.2 仅可观测性栈

需 `--env-file .env` 以注入 oncall-relay 等变量：

```powershell
docker compose -f docker-compose.observability.yml --env-file .env up -d
```

| 服务 | 地址 |
|------|------|
| Grafana | http://localhost:3000（默认 `admin` / `admin`） |
| Prometheus | http://localhost:9090 |
| Alertmanager | http://localhost:9093 |
| Loki | http://localhost:3100 |
| Tempo | gRPC `4317`，HTTP `3200` |
| Oncall relay | http://localhost:8787 |

停止：

```powershell
docker compose -f docker-compose.observability.yml down
```

### 2.3 一键：应用 + 数据库 + 可观测性栈

```powershell
docker compose -f docker-compose.yml -f docker-compose.observability.yml --env-file .env up -d --build
```

停止并移除容器：

```powershell
docker compose -f docker-compose.yml -f docker-compose.observability.yml down
```

### 2.4 Compose 部署注意事项

**指标采集**

`observability/prometheus/prometheus.yml` 中 myapp 的抓取目标为 `host.docker.internal:8000`（经宿主机端口访问 app 容器的 `/metrics`）。Docker Desktop（Windows/macOS）通常可用；Linux Docker 需在 Prometheus 容器内把该别名映射到宿主机网关，`docker-compose.observability.yml` 已通过 `extra_hosts: ["host.docker.internal:host-gateway"]` 固化该映射。

Linux 下可用以下命令从 Prometheus 容器内验证：

```bash
docker compose -f docker-compose.observability.yml exec prometheus \
  wget -qO- http://host.docker.internal:8000/metrics
```

- 返回 Prometheus 文本指标：抓取链路正常。
- `bad address` / `no such host`：宿主机别名未解析，检查 `extra_hosts` 是否生效。
- `connection refused`：别名已解析，但宿主机 `8000` 没有应用监听，检查 app 容器、端口映射和 `/health/live`。

**应用日志 → Loki**

Promtail 读取宿主机 `./logs/*.jsonl`（容器内 `/mnt/myapp-logs`）。`docker-compose.yml` 中 app 已默认设置 `LOG_FILE=/var/log/myapp/myapp.jsonl` 并挂载 `./logs`，与观测栈合并启动后 **Loki 可采集应用 JSON 日志**。

本地 Poetry 运行时，在 `.env` 中设置 `LOG_FILE=logs/myapp.jsonl` 即可写入同一目录。

**OpenTelemetry**

Compose 中 app 默认 `OTEL_ENABLED=false`。使用 Tempo 时需在 app 侧开启 OTEL，并将 endpoint 指向 Tempo（如 `http://host.docker.internal:4317`）。

**自动运维**

告警 → relay → GitHub / Cursor 的完整链路见 [自动运维 Runbook](auto-ops.md)。

---

## 三、Kubernetes

清单文件：`deploy/k8s/deployment-hpa.yaml`（单文件包含 Deployment、Service、HPA）。

> 从 Compose 全栈迁到 K8s 的完整 checklist 见 [K8s 升级方案模板](../templates/k8s-upgrade-template.md)。

### 3.1 包含的资源

| 资源 | 说明 |
|------|------|
| Deployment `myapp` | 2 副本起，镜像 `myapp:latest`，探针 `/health/live`、`/health/ready` |
| Service `myapp` | ClusterIP，80 → 8000 |
| HPA `myapp-hpa` | min 2 / max 10，CPU 70%、内存 80% |

**不包含**：PostgreSQL、Loki、Promtail、Prometheus、Grafana（需自行准备或使用托管服务）。

### 3.2 部署步骤

1. **构建并推送镜像**（将 YAML 中的 `myapp:latest` 改为你的镜像地址）：

   ```powershell
   docker build -t your-registry/myapp:1.0.0 .
   docker push your-registry/myapp:1.0.0
   ```

2. **创建数据库 Secret**（连接串与集群内 Postgres 或云 RDS 一致）：

   ```bash
   kubectl create secret generic myapp-secrets \
     --from-literal=database-url='postgresql+asyncpg://user:pass@host:5432/myapp'
   ```

3. **应用清单**：

   ```bash
   kubectl apply -f deploy/k8s/deployment-hpa.yaml
   ```

4. **验证**：

   ```bash
   kubectl get pods,svc,hpa -l app=myapp
   kubectl port-forward svc/myapp 8080:80
   # 访问 http://127.0.0.1:8080/health/ready
   ```

5. **数据库 schema**（在可连库的环境执行）：

   ```powershell
   poetry run alembic upgrade head
   ```

### 3.3 扩缩容说明

HPA **仅针对 myapp Pod**。PostgreSQL、Loki、Promtail 等：

- 不在本仓库 K8s 清单中；
- 通常采用托管数据库、DaemonSet 采集日志、独立 observability 集群等方案；
- 高延迟/QPS 告警可能需修代码或 DB，而非扩容观测组件。

HPA 参数调整与 `scale-advisory` 告警见 [自动运维 Runbook — 自动扩容](auto-ops.md)。

---

## 四、部署方式对照

| 方式 | 适用 | 命令摘要 |
|------|------|----------|
| Poetry + Docker Postgres | 日常开发 | `docker compose up -d postgres` + `poetry run myapp` |
| Compose 应用栈 | 本地/demo 一体化 | `docker compose up -d --build` |
| Compose 观测栈 | 指标/告警/ Grafana | `docker compose -f docker-compose.observability.yml --env-file .env up -d` |
| Compose 全栈 | app + DB + 观测 | 两个 `-f` 合并（见 2.3） |
| Kubernetes | 生产无状态应用层 | `kubectl apply -f deploy/k8s/deployment-hpa.yaml` |

---

## 五、相关文档

- [自动运维 Runbook](auto-ops.md)
- [GitHub Actions 工作流](../github-workflows/README.md)
- [架构总览](../architecture/overview.md)
- 仓库 `README.md`、`AGENTS.md`
