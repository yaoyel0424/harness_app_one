# FastAPI 全栈后端工程模板

涵盖 **开发 → 质量门禁 → CI/CD → 可观测性 → 安全** 的完整 Python 后端技术栈。

## 技术栈一览

| 层次 | 技术 |
|------|------|
| Web 框架 | FastAPI, Uvicorn, Gunicorn |
| 依赖管理 | Poetry, pyenv (`.python-version`) |
| 代码质量 | Ruff (lint+format), mypy, Bandit |
| 架构约束 | import-linter, pytest-archon |
| 测试 | pytest, pytest-cov, pytest-asyncio, pytest-xdist, testcontainers, respx |
| CI/CD | GitHub Actions, Docker 多阶段构建 |
| 可观测性 | Prometheus, Loki, Grafana, OpenTelemetry, Tempo |
| 安全 | pip-audit, gitleaks, Dependabot, Renovate, CycloneDX SBOM |
| 文档 | MkDocs Material, ADR, AGENTS.md |
| 数据库 | SQLAlchemy 2.0 async, Alembic, PostgreSQL |

## 快速开始

### 前置条件

- Python 3.12（推荐 pyenv）
- [Poetry](https://python-poetry.org/)
- Docker（集成测试与可观测性栈）

### Windows 用户

`Makefile` 依赖 `make` 工具。Windows 下可直接使用 Poetry 命令：

```powershell
poetry install --with dev
poetry run pytest tests/unit tests/architecture -n auto
poetry run myapp
```

可选：安装 [uv](https://github.com/astral-sh/uv) 加速依赖安装（导出 requirements 后使用）：

```powershell
poetry export --format requirements.txt --output requirements.txt --without-hashes
uv pip install -r requirements.txt
```

### 安装与运行

```bash
# 安装依赖
poetry install --with dev

# 安装 pre-commit 钩子
poetry run pre-commit install

# 启动开发服务器
poetry run myapp
# 或
make run
```

访问：

- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health/live
- Prometheus 指标：http://127.0.0.1:8000/metrics

### 常用命令

```bash
make help          # 查看全部命令
make check         # lint + typecheck + security + arch + test
make test          # 单元测试（并行）
make integration   # 集成测试（需 Docker）
make docs          # 构建文档
make sbom          # 生成 SBOM
```

## 目录结构

```
src/myapp/
├── api/           # 路由层
├── core/          # 业务层
├── db/            # 数据访问层
├── schemas/       # Pydantic 模型
├── utils/         # 日志、HTTP 客户端、OTel
├── config.py      # 配置
└── main.py        # 入口

tests/
├── unit/
├── integration/
└── architecture/
```

## Docker

```bash
# 应用 + PostgreSQL
docker compose up -d

# 可观测性栈（Prometheus + Loki + Grafana + Tempo + Alertmanager）
docker compose -f docker-compose.observability.yml --env-file .env up -d
```

## 自动运维（日志跟踪 / 自动修复 / 自动提交 / 扩容）

告警 → `oncall-relay` → GitHub Actions → Cursor Cloud Agent 开 PR → CI → 可选自动 merge。

1. 复制 `.env.example` 为 `.env`，填入 `GITHUB_TOKEN`、`GITHUB_REPO`（见文件底部「自动运维」章节）
2. 在 GitHub 配置 Secrets：`CURSOR_API_KEY`、`ONCALL_WEBHOOK_SECRET`
3. 启动观测栈（见上）
4. 可选：`LOG_FILE=logs/myapp.jsonl` 让 Promtail 采集应用日志
5. **Cursor Automation**：见 [`.cursor/automations/README.md`](.cursor/automations/README.md)

详细说明：[docs/runbooks/auto-ops.md](docs/runbooks/auto-ops.md)

## 环境变量

复制 `.env.example` 为 `.env` 并按需修改：

```bash
cp .env.example .env
```

## 文档

- 在线文档：`poetry run mkdocs serve`
- AI/新人导航：见 [AGENTS.md](AGENTS.md)

## 许可证

MIT
