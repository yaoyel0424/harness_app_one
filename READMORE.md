下面给出一个**全面的 Python 后端工程架构**，涵盖从开发、构建、质量门禁到运维可观测性的完整技术栈，并说明每项技术的具体作用。

该架构以 **FastAPI + Poetry + Ruff + mypy + pytest + Prometheus + Loki** 为核心，适用于中大型项目或团队协作场景。

---

## 一、总体架构分层

| 层次 | 目标 | 关键技术 |
|------|------|----------|
| **开发环境层** | 统一开发者环境、依赖管理 | `pyenv` / `.python-version`, `Poetry` / `uv`, `pre-commit` |
| **代码质量层** | 静态检查、格式化、类型安全 | `Ruff` (Linter + Formatter), `Black`, `mypy`, `Bandit` |
| **架构约束层** | 强制分层依赖、防止反模式 | `import-linter`, `pytest-archon`, `pylint` (自定义规则) |
| **测试与覆盖率层** | 单元测试、集成测试、覆盖率门禁 | `pytest`, `pytest-cov`, `pytest-asyncio`, `pytest-env`, `testcontainers` |
| **CI/CD 层** | 自动化验证、构建、发布 | GitHub Actions / GitLab CI, `setup-python`, `poetry`, `Docker Build` |
| **运行与可观测层** | 性能监控、日志聚合、健康检查 | `Prometheus`, `Loki`, `Grafana`, `OpenTelemetry`, `Uvicorn` + `/health` |
| **安全与依赖层** | 依赖漏洞扫描、版本锁定 | `pip-audit` / `safety`, `Dependabot` / `Renovate`, `SBOM` |
| **文档与知识层** | 架构决策、代码导航 | `AGENTS.md`, `docs/`, `MkDocs` / `Material`, `ADR` |

---

## 二、各层技术详解

### 1. 开发环境层

| 技术 | 作用 |
|------|------|
| **`.python-version` + `pyenv`** | 锁定项目 Python 版本（如 3.10），确保所有开发者、CI 环境使用完全一致的 Python 解释器。 |
| **Poetry** | 依赖管理、虚拟环境、锁定文件 (`poetry.lock`)。替代 `pip` + `venv` + `requirements.txt`，支持解析和版本冲突解决。 |
| **`uv`** | 极快的 Poetry 替代品（Rust 实现），用于大型项目加速依赖安装和解析。 |
| **`pre-commit`** | Git 钩子管理器，在 `git commit` 前自动运行 `ruff`、`mypy`、`bandit` 等检查，防止低质量代码进入仓库。 |
| **`Makefile`** | 封装常用命令（`make check`, `make test`, `make cov`），降低认知负担，统一团队操作入口。 |

### 2. 代码质量层

| 技术 | 作用 |
|------|------|
| **Ruff (Linter)** | 极快的 Python linter，集成了 `pycodestyle`, `pyflakes`, `isort`, `flake8-bugbear` 等规则。用于检查代码风格、潜在错误、未使用变量等。 |
| **Ruff (Formatter)** | 替代 `Black` 的代码格式化器，保证统一代码风格（行宽、缩进、换行）。 |
| **Black** | （可选）更稳定的格式化器，与 Ruff 格式化功能类似，二选一即可。 |
| **mypy** | 静态类型检查器，根据类型注解推断错误。在大型项目中显著减少 `AttributeError`、`TypeError` 等运行时错误。 |
| **Bandit** | 安全漏洞扫描器，检测常见安全问题（如 `eval` 执行、硬编码密码、SQL 注入模式）。 |
| **`pylint`** | 可选，提供更深度的代码质量评分和自定义检查器（如禁止使用 `print`）。 |

### 3. 架构约束层

| 技术 | 作用 |
|------|------|
| **import-linter** | 定义和强制模块间的依赖规则。例如：“API 层不能直接导入 Repository 层”，“Service 层不能导入 API 层”。防止代码腐化，保持清晰分层。 |
| **pytest-archon** | 基于 `pytest` 的架构测试库，可以在单元测试中编写类似 ArchUnit 的断言（如“所有以 `ServiceImpl` 结尾的类必须位于 `core` 包下”）。 |
| **自定义 Ruff/Pylint 插件** | 针对项目特定的反模式（如禁止使用 `requests` 直连外部 API，必须通过封装的 HTTP 客户端）编写规则。 |

### 4. 测试与覆盖率层

| 技术 | 作用 |
|------|------|
| **pytest** | 测试框架，支持 fixtures、参数化、插件扩展。替代 `unittest`，更简洁。 |
| **pytest-cov** | 测量测试覆盖率（语句、分支、行），并可设置最低阈值（如 `--cov-fail-under=80`）。 |
| **pytest-asyncio** | 支持异步代码测试（FastAPI 的异步路由、异步数据库调用）。 |
| **pytest-env** | 在测试运行前设置环境变量，避免污染开发环境配置。 |
| **pytest-xdist** | 并行运行测试，加速 CI 流程。 |
| **testcontainers** | 在测试中启动真实的 Docker 容器（PostgreSQL, Redis），用于集成测试，避免 mock 过度的虚假绿色测试。 |
| **`responses` / `respx`** | HTTP 请求模拟库，用于测试外部 API 调用。 |

### 5. CI/CD 层

| 技术 | 作用 |
|------|------|
| **GitHub Actions / GitLab CI** | 自动化流水线：代码检出 → 安装 Python → 安装依赖 → 运行 Linter → 类型检查 → 安全扫描 → 架构测试 → 单元/集成测试 → 覆盖率门禁 → 构建 Docker 镜像 → 推送至注册表。 |
| **`setup-python` (GitHub Action)** | 在 CI 中安装指定 Python 版本，支持缓存，加速依赖安装。 |
| **`poetry` 安装与缓存** | 利用 `poetry export` + `pip cache` 或 `actions/cache` 缓存虚拟环境，加速 CI。 |
| **Docker Build + BuildKit** | 将应用打包为轻量级镜像（使用 `python:3.10-slim` 基础镜像），支持多阶段构建。 |
| **`docker-compose`** | 在 CI 中启动依赖服务（数据库、消息队列）用于集成测试。 |

### 6. 运行与可观测层

| 技术 | 作用 |
|------|------|
| **Uvicorn / Gunicorn** | ASGI 服务器，运行 FastAPI 应用。生产环境推荐 `Gunicorn + Uvicorn workers`。 |
| **`/health` 端点** | 实现 `GET /health` 返回 200，用于容器编排（K8s 就绪探针）和负载均衡健康检查。 |
| **`/metrics` 端点** | 通过 `prometheus-fastapi-instrumentator` 自动暴露 Prometheus 格式的指标（请求数、延迟、错误率等）。 |
| **Prometheus** | 指标收集和时序数据库，定期从 `/metrics` 拉取数据，存储并支持告警规则。 |
| **Loki** | 日志聚合系统，配合 `promtail` 采集容器日志，使用标签查询。 |
| **Grafana** | 可视化仪表盘，对接 Prometheus 和 Loki，展示 QPS、错误率、日志流。 |
| **OpenTelemetry** | 分布式追踪（可选），与 `Jaeger` 或 `Tempo` 集成，用于排查链路性能瓶颈。 |
| **`python-json-logger`** | 将日志输出为 JSON 格式，便于 Loki 解析和索引字段。 |
| **`loguru`** | 更友好的日志库，可配置 JSON 格式和异步 sink。 |

### 7. 安全与依赖层

| 技术 | 作用 |
|------|------|
| **`pip-audit` / `safety`** | 扫描依赖包中的已知漏洞（基于 CVE 数据库），在 CI 中阻断构建。 |
| **Dependabot (GitHub)** | 每周自动检查依赖更新，并提交 PR。可通过 `ignore` 规则限制大版本升级（如禁止 Python 升级到 3.11+）。 |
| **Renovate** | 更灵活的依赖更新工具，支持自定义分组、时间计划、版本约束。 |
| **`sbom` 生成 (如 `cyclonedx`)** | 生成软件物料清单，用于供应链安全审计。 |
| **`secrets` 扫描 (如 `gitleaks`)** | 防止密码、API 密钥误提交到仓库。 |

### 8. 文档与知识层

| 技术 | 作用 |
|------|------|
| **`AGENTS.md`** | 为 AI 或新成员提供项目“说明书”，包含技术栈、目录结构、常用命令、关键约定。 |
| **`docs/` 结构化目录** | 存放架构设计、编码规范、ADR（架构决策记录）。 |
| **MkDocs + Material 主题** | 将 `docs/` 下的 Markdown 文件渲染为静态站点，托管在 GitHub Pages 或内部 Wiki。 |
| **`adr-tools`** | 命令行工具创建和管理 ADR，记录重要架构决策及其背景。 |
| **`pydoc-markdown`** | 从代码 docstring 生成 API 文档。 |

---

## 三、完整工具链汇总表（按用途）

| 用途类别 | 推荐技术 | 作用简述 |
|----------|----------|----------|
| **版本锁定** | `pyenv` + `.python-version` | 统一 Python 版本 |
| **依赖管理** | Poetry / uv | 锁定依赖版本，虚拟环境 |
| **代码格式化** | Ruff (format) / Black | 统一代码风格 |
| **代码检查** | Ruff (lint) | 静态分析、错误检测 |
| **类型检查** | mypy | 利用类型注解避免运行时错误 |
| **安全扫描** | Bandit, pip-audit | 漏洞和代码安全风险 |
| **架构约束** | import-linter, pytest-archon | 强制分层、禁止违规导入 |
| **测试框架** | pytest + pytest-cov | 编写和执行测试，生成覆盖率 |
| **集成测试** | testcontainers | 真实依赖容器化测试 |
| **CI 流水线** | GitHub Actions | 自动化验证、构建 |
| **Web 框架** | FastAPI | 构建 REST/异步 API |
| **服务器** | Uvicorn / Gunicorn | ASGI 服务器 |
| **指标监控** | Prometheus + `/metrics` | 收集应用性能指标 |
| **日志聚合** | Loki + promtail | 集中查询日志 |
| **可视化** | Grafana | 仪表盘展示指标和日志 |
| **依赖更新** | Dependabot / Renovate | 自动更新依赖并防误升级 |
| **文档站点** | MkDocs | 生成项目文档网站 |
| **本地钩子** | pre-commit | commit 前自动检查 |

---

## 四、与 Java/Spring 版对照（帮助理解迁移）

| Java 版技术 | Python 版技术 | 作用对照 |
|-------------|---------------|----------|
| Maven / Gradle | Poetry / uv | 构建和依赖管理 |
| JUnit 5 | pytest | 单元测试框架 |
| JaCoCo | pytest-cov | 测试覆盖率 |
| Checkstyle | Ruff (lint) | 代码风格检查 |
| SpotBugs | Bandit + mypy | 缺陷与安全扫描 |
| ArchUnit | import-linter / pytest-archon | 架构约束测试 |
| Spring Boot Actuator | `/health`, `/metrics` 端点 | 运行时信息暴露 |
| Micrometer | prometheus-fastapi-instrumentator | Prometheus 指标集成 |
| Logback + ELK/Loki | `python-json-logger` + Loki | 日志结构化与聚合 |
| Maven Enforcer | `pyproject.toml` python 约束 + Poetry `~=` | 版本锁定 |
| Git Worktree 验证脚本 | 同 Shell 脚本 + Uvicorn 启动 | 隔离环境集成测试 |

---

## 五、推荐的目录结构

```
my-project/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                # 主 CI
│   │   ├── dependency-update.yml # Dependabot / Renovate
│   ├── dependabot.yml
├── .python-version               # 3.10.15
├── .pre-commit-config.yaml
├── Makefile
├── pyproject.toml                # Poetry + Ruff + mypy + pytest 配置
├── poetry.lock                   # 依赖锁定文件
├── README.md
├── AGENTS.md                     # 导航与约定
├── scripts/
│   ├── validate_worktree.sh
│   ├── cleanup_agent.py
│   ├── check_doc_freshness.py
├── docs/
│   ├── architecture/
│   ├── standards/
│   ├── templates/
│   └── adr/
├── src/
│   └── myapp/
│       ├── __init__.py
│       ├── main.py               # FastAPI 入口
│       ├── api/                  # 路由层
│       ├── core/                 # 业务层
│       ├── db/                   # 数据访问层
│       ├── models/               # Pydantic / ORM 模型
│       ├── utils/
│       └── config.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── architecture/             # 存放 import-linter 和 pytest-archon 测试
│   └── conftest.py
└── docker-compose.observability.yml  # Prometheus + Loki + Grafana
```

---

## 六、总结

该工程架构覆盖了从**编写代码 → 质量保障 → 自动化验证 → 生产可观测**的完整链路，所有技术均具备：

- **明确的作用**（不引入无价值的工具）
- **良好的生态兼容性**（FastAPI 原生支持 Prometheus，pytest 插件丰富）
- **可渐进落地**（可先启用 lint+test，后续再添加 import-linter 和观测栈）

如果你需要以上任一技术的**具体配置代码片段**（如 `pyproject.toml` 完整示例、`import-linter` 规则、`validate_worktree.sh` 脚本），我可以继续提供。