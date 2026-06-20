# 财务向量审计项目 - 当前环境识别报告

## 1. Summary

本计划针对用户 `/plan 识别一下环境` 的请求，输出当前工作区的环境识别结论。识别范围覆盖：

- 操作系统与终端环境。
- 编程语言与工具链可用性。
- 项目结构与代码完整度。
- 关键服务（PostgreSQL / Redis / Qdrant / 后端 / 前端）的运行状态。
- 已通过的验证与已知阻塞项。
- 后续可选的下一步动作（需用户确认后才会执行）。

由于任务性质是"识别/盘点"，本计划本身不修改任何业务文件，只输出一份环境清单和候选行动方案。

## 2. Current State Analysis

### 2.1 操作系统与终端

- 操作系统：Windows。
- PowerShell 5（`powershell5`）环境。
- 当前工作目录：

  ```text
  E:\projects\finance-vector-audit\wroksapce20260616
  ```

### 2.2 工具链可用性（已探测）

| 工具 | 状态 | 备注 |
| --- | --- | --- |
| Python | 可用 | `Python 3.13.1`（`C:\Users\banmao\AppData\Local\Programs\Python\Python313\python.exe`） |
| pip | 可用 | `pip 24.3.1`（随系统 Python） |
| Node.js | 可用 | `v25.4.0` |
| npm | 可用 | `11.7.0` |
| pnpm | 可用 | `9.0.0` |
| Docker | **不可用** | `docker: 无法将"docker"项识别为 cmdlet` |
| docker compose | **不可用** | 同样未被识别 |
| Qdrant（端口 6333） | 未运行 | `Test-NetConnection` 返回 `False` |
| PostgreSQL（端口 5432） | 未运行 | `Test-NetConnection` 返回 `False` |
| Redis（端口 6379） | 未运行 | `Test-NetConnection` 返回 `False` |
| 后端 FastAPI（端口 8000） | 未运行 | `Test-NetConnection` 返回 `False` |

> 结论：本机具备 Python、Node、pnpm 工具链，但 Docker 未安装，因此 `docker compose up -d` 在当前环境无法执行；PostgreSQL / Redis / Qdrant 三个外部依赖服务均未启动。

### 2.3 已有项目文件（与历史规划一致）

```text
README.md
package.json
pnpm-workspace.yaml
pnpm-lock.yaml
docker-compose.yml
.env.example
backend/                (完整 FastAPI 工程)
frontend/               (完整 Vite + React + TS 工程，含 dist/ 构建产物)
.trae/documents/        (历史计划与进展报告)
.trae/specs/progress-review/  (规范、清单、任务文档)
```

#### 后端结构（已实现）

```text
backend/
  pyproject.toml
  app/
    main.py
    core/config.py
    db/session.py
    db/models.py            (Organization/ImportJob/SourceFile/AccountingEntry/EntryTag/
                             DocumentChunk/AuditRisk/RiskEvidence/ReviewAction)
    api/                    (routes_imports.py / routes_entries.py /
                             routes_files.py / routes_risks.py)
    schemas/                (import_job.py / accounting_entry.py / risk.py)
    services/               (file_parser_service / import_service / tagging_service /
                             embedding_service / vector_store_service /
                             risk_rule_service / risk_analysis_service / redaction_service)
    storage/local_storage.py
  tests/test_app.py
  finance_audit.db          (本地 SQLite 数据文件)
```

依赖（pyproject.toml 声明）：

```text
fastapi>=0.111.0
uvicorn[standard]>=0.30.0
sqlalchemy>=2.0.30
psycopg[binary]>=3.1.19
pydantic-settings>=2.3.0
python-multipart>=0.0.9
pandas>=2.2.2
openpyxl>=3.1.4
pdfplumber>=0.11.0
qdrant-client>=1.9.1
httpx>=0.27.0
pytest>=8.2.0
```

#### 前端结构（已实现）

```text
frontend/
  package.json
  index.html
  vite.config.ts
  tsconfig.json
  src/
    main.tsx / App.tsx
    api/client.ts
    components/ (Layout / FileUploader / RiskBadge)
    pages/      (DashboardPage / ImportPage / EntriesPage / RisksPage / RiskDetailPage)
    styles.css
  dist/        (已存在构建产物，说明构建流程至少成功过一次)
```

#### 关键脚本（根 package.json）

```text
dev:frontend   -> pnpm --dir frontend dev
build:frontend -> pnpm --dir frontend build
lint:frontend  -> pnpm --dir frontend lint
dev:backend    -> uvicorn app.main:app --app-dir backend --reload
test:backend   -> pytest backend/tests
```

### 2.4 环境变量（`.env.example`）

```text
DATABASE_URL=postgresql+psycopg://finance:finance@localhost:5432/finance_audit
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=accounting_chunks
REDIS_URL=redis://localhost:6379/0
UPLOAD_DIR=storage/uploads
AI_PROVIDER=openai-compatible
AI_BASE_URL=https://api.example.com/v1
AI_API_KEY=replace-me
AI_MODEL=replace-me
EMBEDDING_DIMENSION=384
FRONTEND_API_BASE_URL=http://localhost:8000
```

注：项目根目录下未见 `.env`，后端默认回退到 `sqlite:///./finance_audit.db`，目前已存在该 SQLite 文件，说明在缺少 PostgreSQL 的情况下后端可以本地起 SQLite 运行。

### 2.5 验证历史状态

来自 [project-progress-status-plan.md](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/documents/project-progress-status-plan.md) 的记录：

- `pnpm --dir frontend lint`：通过。
- `pnpm --dir frontend build`：通过（`frontend/dist/` 存在）。
- `python -m pytest backend/tests`：**未通过**。
  - 失败原因：依赖问题，测试运行时 `ModuleNotFoundError: No module named 'sqlalchemy'`。
  - 该问题与代码无关，是 Python 环境未安装依赖所致。

> 当前工作区中 `backend/.venv/` 与 `backend/venv/` 都已存在，说明历史上曾尝试创建虚拟环境，但当前激活状态未知；需在新的执行阶段重新激活并补齐依赖。

### 2.6 关键代码现状要点

- 后端 [main.py](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/main.py) 启动时会 `Base.metadata.create_all(bind=engine)`，可在 SQLite 下自建表。
- 配置 [config.py](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/core/config.py) 默认 `database_url = "sqlite:///./finance_audit.db"`，即无 `.env` 时回退 SQLite。
- [embedding_service.py](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/services/embedding_service.py) 当前是占位实现（基于 token hash + L2 归一化），不依赖外部模型，可离线运行。
- [vector_store_service.py](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/services/vector_store_service.py) 在 `VectorStore.__init__` 中直接连接 Qdrant；当 Qdrant 不可用时 `safe_vector_store()` 会返回 `None`，需要服务层对 None 做容错。
- [risk_rule_service.py](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/services/risk_rule_service.py) 已实现大额整数、弱摘要、期末大额、往来挂账、重复交易五类规则，可纯 CPU 运行。

## 3. Proposed Changes

本计划任务本身是"识别环境"，因此默认不产生代码改动。下面给出可选的后续行动（执行阶段前需用户确认）。

### 3.1 选项 A：保持识别报告，不执行任何变更

仅输出本计划，由用户决定下一步。

### 3.2 选项 B：搭建最小可运行闭环（推荐）

在用户确认后执行：

1. 修复后端 Python 环境：
   - 激活 `backend/.venv`（或重新创建）。
   - `pip install -e .`。
   - 运行 `pytest backend/tests` 验证。
2. 保持 SQLite 默认（不依赖 Docker / PostgreSQL），启动后端：
   - `uvicorn app.main:app --app-dir backend --reload`。
3. 处理 Qdrant 缺失：
   - 如用户希望保留 Qdrant：需要安装 Docker 或直接下载 Qdrant 二进制。
   - 如仅做端到端冒烟：可临时禁用向量写入/检索路径，验证业务接口。
4. 启动前端 `pnpm --dir frontend dev`，并通过 `http://localhost:5173` 访问。
5. 跑通最小路径：创建导入任务 → 上传 CSV → 处理 → 查询分录 → 查询风险。

### 3.3 选项 C：补齐依赖服务

- 安装 Docker Desktop 后 `docker compose up -d`。
- 或仅本地安装 Qdrant 单二进制，PostgreSQL 继续用 SQLite。
- 安装完成后再次执行 [3.2] 的步骤。

## 4. Assumptions & Decisions

1. 用户当前请求是"识别环境"，因此本计划不修改任何业务代码或环境变量。
2. 工具链（Python / Node / pnpm）已具备，Docker 暂不可用是已知约束。
3. PostgreSQL / Redis / Qdrant 三个外部依赖服务当前全部未启动。
4. 后端默认走 SQLite，理论上仅靠本地工具链即可启动后端；Qdrant 缺失只会影响向量相关接口。
5. 历史进展报告中的"后端测试未通过"是依赖问题，不属于代码缺陷。
6. 是否继续推进到实际执行（选项 B/C）由用户决定。

## 5. Verification Steps

在用户选择选项 B/C 并进入执行阶段后，建议先做以下自检：

```powershell
# 1. 验证 Python / Node 工具链
python --version
pip --version
node --version
pnpm --version

# 2. 验证后端依赖
cd backend
.\.venv\Scripts\Activate.ps1
pip install -e .
pytest tests

# 3. 验证后端启动
uvicorn app.main:app --app-dir backend --reload
# 浏览器访问 http://localhost:8000/health 应返回 {"status":"ok"}

# 4. 验证前端
cd ..\frontend
pnpm install
pnpm lint
pnpm build
pnpm dev
```

如选择选项 C，额外验证：

```powershell
docker --version
docker compose version
docker compose up -d
docker compose ps
```

## 6. Out of Scope

本计划不涉及：

- 任何业务代码修改。
- 数据库迁移、模型变更。
- Docker 安装。
- 部署到生产环境。
- 多租户、权限、计费等后续阶段功能。
