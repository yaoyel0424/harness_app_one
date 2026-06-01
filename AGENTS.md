# AGENTS.md — 项目导航与约定

> 供 AI Agent 与新成员快速了解本项目的"说明书"。

## 项目概述

- **名称**：myapp
- **类型**：FastAPI 异步 REST API
- **Python 版本**：3.12（见 `.python-version`）
- **包管理**：Poetry（`pyproject.toml` + `poetry.lock`）

## 目录结构

| 路径 | 用途 |
|------|------|
| `src/myapp/api/` | HTTP 路由，禁止直接导入 `myapp.db` |
| `src/myapp/core/services/` | 业务逻辑 Service 类 |
| `src/myapp/db/repositories/` | 数据访问 Repository |
| `src/myapp/schemas/` | Pydantic 请求/响应模型 |
| `src/myapp/composition/` | 组合根 / FastAPI Depends 注入 |
| `src/myapp/utils/` | 日志、HTTP 客户端、OpenTelemetry |
| `tests/unit/` | 单元测试 |
| `tests/integration/` | testcontainers 集成测试 |
| `tests/architecture/` | import-linter + pytest-archon |
| `docs/` | MkDocs 文档与 ADR |
| `observability/` | Prometheus/Loki/Grafana/Tempo 配置 |
| `scripts/` | 工具脚本 |

## 常用命令

```bash
make install       # poetry install
make check         # 全部质量门禁
make test          # 单元 + 架构测试
make integration   # Docker 集成测试
make run           # 启动开发服务器
make docs          # 构建 MkDocs
make validate-worktree  # 完整 worktree 验证
```

## 架构约束

1. **API 层** → 只能依赖 `core`、`schemas`、`dependencies`
2. **Core 层** → 可依赖 `db`、`schemas`、`utils`，禁止依赖 `api`
3. **DB 层** → 只含 ORM 与 Repository，禁止依赖 `api` 或 `core`
4. 外部 HTTP 调用必须通过 `utils/http_client.py`，禁止直接使用 `requests`

验证：`make arch` 或 `poetry run lint-imports`

## 代码质量工具

| 工具 | 配置位置 | 命令 |
|------|----------|------|
| Ruff | `pyproject.toml [tool.ruff]` | `make lint` / `make format` |
| mypy | `pyproject.toml [tool.mypy]` | `make typecheck` |
| Bandit | `pyproject.toml [tool.bandit]` | `make security` |
| import-linter | `pyproject.toml [tool.importlinter]` | `make arch` |
| pre-commit | `.pre-commit-config.yaml` | 自动于 git commit |

## 测试约定

- 覆盖率门禁：**80%**
- 单元测试用 SQLite 内存库（`conftest.py`）
- 集成测试用 testcontainers PostgreSQL（`@pytest.mark.integration`）
- HTTP mock 用 **respx**

## 可观测性

| 端点/组件 | 说明 |
|-----------|------|
| `GET /health/live` | K8s 存活探针 |
| `GET /health/ready` | K8s 就绪探针（含 DB 检查） |
| `GET /metrics` | Prometheus 指标 |
| JSON 日志 | stdout 或 `LOG_FILE=logs/myapp.jsonl`，供 Loki/Promtail 采集 |
| OpenTelemetry | 设置 `OTEL_ENABLED=true` 启用 |

## 自动运维

| 组件 | 路径 |
|------|------|
| 告警规则 | `observability/prometheus/alerts.yml` |
| Alertmanager | `observability/alertmanager/alertmanager.yml` |
| Webhook 中继 | `scripts/oncall_relay.py` |
| AI 值班 (SDK) | `scripts/ai_oncall.py` |
| **Cursor Automation** | `.cursor/automations/*.yaml` |
| GHA 工作流 | `.github/workflows/oncall-dispatch.yml` |
| 自动合并 | `.github/workflows/auto-merge.yml`（需 `AUTO_MERGE_ENABLED=true`） |
| K8s HPA | `deploy/k8s/deployment-hpa.yaml` |

Runbook：[docs/runbooks/auto-ops.md](docs/runbooks/auto-ops.md)

## 环境变量

见 `.env.example`。关键变量：

- `DATABASE_URL` — 异步数据库连接串
- `APP_ENV` — development / test / production
- `OTEL_ENABLED` — 是否启用分布式追踪
- `LOG_LEVEL` — 日志级别
- `LOG_FILE` — 可选，JSONL 文件路径供 Promtail 采集
- `GITHUB_TOKEN` / `GITHUB_REPO` — 自动运维 relay（见 `.env.example` 底部）

## 提交前检查清单

- [ ] `make check` 通过
- [ ] 新增 API 有对应测试
- [ ] 架构变更更新了 `docs/adr/`
- [ ] 无密钥泄露（gitleaks 自动检查）

## 禁止事项

- 不要在 `api/` 中写 SQL 或直接操作 ORM
- 不要跳过 import-linter 约束
- 不要提交 `.env` 文件
- 不要使用 `print()` 代替日志（测试除外）
