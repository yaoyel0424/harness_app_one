# 测试规范

## 目录结构

```
tests/
├── unit/           # 单元测试（mock 外部依赖）
├── integration/    # 集成测试（testcontainers + 真实 PostgreSQL）
├── architecture/   # 架构约束测试（import-linter、pytest-archon）
└── conftest.py     # 全局 fixtures
```

## 运行命令

```bash
make test           # 单元 + 架构测试（并行）
make integration    # 集成测试（需要 Docker）
make cov            # 带覆盖率（门禁 80%）
```

## 约定

- 单元测试不依赖 Docker，使用 SQLite 内存库或 mock
- 集成测试标记 `@pytest.mark.integration`
- 架构测试标记 `@pytest.mark.architecture`
- HTTP 外部调用使用 **respx** mock
- 异步测试使用 **pytest-asyncio**（auto 模式）

## 覆盖率

- 最低阈值：80%（`--cov-fail-under=80`）
- CI 上传 coverage.xml 至 Codecov（可选）
