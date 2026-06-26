# 审计风险识别系统

这是一个 Web SaaS 形态的财务软件 MVP，第一阶段聚焦会计凭证导入、原始文件向量化、自动标签和审计风险识别。

## 标准技术栈

### 前端

- React 18
- TypeScript
- Vite 5
- Ant Design 6
- react-router-dom 7
- 原生 `fetch`
- 包管理器统一使用 `pnpm`

### 后端

- Python 3.11+
- FastAPI
- Uvicorn
- SQLAlchemy 2
- Pydantic Settings
- pytest

### 数据与依赖服务

- 本地快速开发默认使用 SQLite：`backend/finance_audit.db`
- 服务化数据库使用 PostgreSQL：`127.0.0.1:5432`
- 向量库使用 Qdrant：`127.0.0.1:6333`
- Redis 当前为预留配置，不是当前必需运行依赖

## 核心能力

- 创建企业/账套导入批次。
- 上传 Excel / CSV 会计分录文件。
- 上传 PDF / TXT 原始文件并抽取文本。
- 自动解析会计分录并生成初始标签。
- 将分录和文件片段写入 Qdrant 向量库。
- 基于规则识别大额整数金额、摘要异常、期末大额交易、往来挂账、重复交易等风险。
- 前端展示导入批次、分录列表、风险列表、证据链和复核操作。
- 创建账套时可指定会计时间线起点，系统按该日期自动生成首个开放会计期间。

## 本地开发

本地开发统一使用 `127.0.0.1`，避免 Windows 下 `localhost`、IPv4、IPv6 解析不一致。

### 1. 安装依赖

前端：

```powershell
pnpm --dir frontend install
```

后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
```

### 2. 启动依赖服务

如果需要 PostgreSQL、Redis、Qdrant：

```powershell
docker compose up -d
```

如果未配置 PostgreSQL，后端默认使用 SQLite 文件：

```text
backend/finance_audit.db
```

### 3. 后端

从项目根目录启动：

```powershell
pnpm dev:backend
```

等价命令：

```powershell
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

后端健康检查：

```text
GET http://127.0.0.1:8000/health
```

### 4. 前端

从项目根目录启动：

```powershell
pnpm dev:frontend
```

默认访问：

```text
http://127.0.0.1:5173
```

前端默认通过 Vite proxy 请求后端：

```text
127.0.0.1:5173/api/* -> 127.0.0.1:8000/api/*
```

## 环境变量

后端实际读取：

```text
backend/.env
```

可以复制根目录模板：

```powershell
Copy-Item .env.example backend/.env
```

前端 API 地址变量统一使用：

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

如果不配置 `VITE_API_BASE_URL`，前端会使用同源 `/api`，由 Vite proxy 转发到后端。

默认 PostgreSQL 配置：

```text
DATABASE_URL=postgresql+psycopg://finance:finance@127.0.0.1:5432/finance_audit
```

## 导入文件字段建议

Excel / CSV 支持中英文字段名，建议包含：

- 凭证号 / voucher_no
- 凭证日期 / voucher_date / date
- 摘要 / summary
- 科目编码 / account_code
- 科目名称 / account_name
- 借方金额 / debit_amount
- 贷方金额 / credit_amount
- 往来单位 / counterparty

## 验证命令

```powershell
python -m pytest backend/tests
pnpm --dir frontend lint
pnpm --dir frontend build
```

## 变更记录与 Agent 集成

- [CHANGELOG.md](./CHANGELOG.md) — 重要功能修复与合并说明
- [CURSOR_GITHUB_SETUP.md](./CURSOR_GITHUB_SETUP.md) — Cursor Cloud Agent 连接 GitHub、创建 PR 的逐步配置
- [AUTOMATIONS_SETUP.md](./AUTOMATIONS_SETUP.md) — 定时测试、Issue 自动开发、PR 合并更新文档
