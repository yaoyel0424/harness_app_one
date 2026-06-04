# myapp 文档中心

欢迎使用 **myapp** —— 基于 FastAPI 的全栈 Python 后端工程模板。

## 快速链接

- [架构总览](architecture/overview.md)
- [编码规范](standards/coding.md)
- [测试规范](standards/testing.md)
- [部署指南](runbooks/deploy.md)
- [自动运维 Runbook](runbooks/auto-ops.md)
- [ADR-0001：记录架构决策](adr/0001-record-architecture-decisions.md)

## 本地预览

```bash
poetry run mkdocs serve
# 或
make docs-serve
```

访问 http://127.0.0.1:8001 查看文档站点。

## Docker 部署

```bash
make docs-up
# 或
docker compose up -d docs --build
```

访问 http://127.0.0.1:8001（与 myapp API 端口 8000 互不冲突）。
