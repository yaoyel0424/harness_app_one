# 架构总览

## 分层结构

```
api/           → HTTP 路由层（FastAPI Router）
composition/   → 组合根 / 依赖注入（FastAPI Depends）
core/          → 业务逻辑层（Service）
db/            → 数据访问层（Repository + ORM）
schemas/       → Pydantic 请求/响应模型
utils/         → 横切关注点（日志、HTTP 客户端、遥测）
```

## 依赖规则（import-linter 强制）

| 源模块 | 禁止直接导入 | 说明 |
|--------|--------------|------|
| `myapp.api` | `myapp.db` | 通过 `composition/` 间接注入 |
| `myapp.core` | `myapp.api` | |
| `myapp.db` | `myapp.api`, `myapp.core` | |

## 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | FastAPI + Uvicorn/Gunicorn |
| 依赖管理 | Poetry |
| 代码质量 | Ruff + mypy + Bandit |
| 架构约束 | import-linter + pytest-archon |
| 测试 | pytest + testcontainers + respx |
| 可观测性 | Prometheus + Loki + Grafana + OpenTelemetry |
| 安全 | pip-audit + gitleaks + Dependabot/Renovate |
| 文档 | MkDocs + ADR |

## 可观测性

- **指标**：`GET /metrics`（Prometheus 格式）
- **健康检查**：`GET /health/live`、`GET /health/ready`
- **日志**：JSON 结构化输出（python-json-logger），由 Promtail 采集至 Loki
- **追踪**：OpenTelemetry OTLP → Tempo

启动观测栈：

```bash
docker compose -f docker-compose.observability.yml up -d
```
