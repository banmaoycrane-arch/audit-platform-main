# 技术栈一致性与公共参数边界治理计划

## Summary

本计划用于识别当前工作区各文件中的技术栈、依赖管理、通信方式、端口、进程、环境变量和数据库路径是否统一，避免因为技术栈选择或公共参数冲突造成“服务不可用、登录失败、配置丢失、接口 404”等低级内部通信错误。

本计划属于：

```text
Domain: D12 - 缺陷修复与环境诊断
Status: engineering-governance
Owner Spec: fix-register-and-backend-availability / task-governance-and-sequencing-plan
```

本计划只治理工程边界，不改变财务业务规则。

## Current State Analysis

### 1. 角色与任务边界

依据 `.trae/rules/project_rules.md`：

- 用户是专业会计师、项目决策者、编程初学者。
- AI 是技术实现者、编程知识补充者、财务视角翻译者。
- 每个任务必须先识别需求域，明确 In Scope / Out of Scope。

因此，本任务不是“继续做新业务功能”，而是先把技术栈和公共参数统一，减少低级通信问题对业务验收的干扰。

### 2. 前端技术栈现状

关键文件：

- `frontend/package.json`
- `frontend/vite.config.ts`
- `frontend/src/api/client.ts`

当前前端技术栈：

| 项目 | 当前使用 |
|---|---|
| 框架 | React 18 |
| 语言 | TypeScript |
| 构建工具 | Vite 5 |
| UI 组件 | Ant Design 6 |
| 路由 | react-router-dom 7 |
| HTTP 请求 | 原生 fetch |
| 类型检查 | `tsc --noEmit` |
| 构建命令 | `tsc -b && vite build` |

当前 `frontend/package.json`：

```text
dev: vite
build: tsc -b && vite build
lint: tsc --noEmit
```

注意：当前 `lint` 实际是 TypeScript 类型检查，不是 ESLint。

### 3. 后端技术栈现状

关键文件：

- `backend/pyproject.toml`
- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/db/session.py`
- `backend/app/core/security.py`

当前后端技术栈：

| 项目 | 当前使用 |
|---|---|
| 语言 | Python 3.11+ |
| Web 框架 | FastAPI |
| ASGI Server | Uvicorn |
| ORM | SQLAlchemy 2 |
| 配置 | pydantic-settings |
| 数据库 | PostgreSQL / SQLite fallback |
| 向量库 | Qdrant，支持远程失败后本地 path 降级 |
| 文件解析 | pandas / openpyxl / pdfplumber |
| 外部 HTTP | httpx |
| 测试 | pytest |

后端入口是：

```text
backend/app/main.py -> app.main:app
```

健康检查：

```text
GET /
GET /health
```

### 4. 当前已识别的技术栈与公共参数冲突

#### 4.1 后端端口 8000 / 8010 不统一

相关文件：

- `README.md`
- `package.json`
- `frontend/vite.config.ts`
- `.env.example`

当前冲突：

| 来源 | 后端端口 |
|---|---:|
| README 后端启动说明 | 8000 |
| README 健康检查 | 8000 |
| Vite proxy | 8000 |
| 根 `package.json` 的 `dev:backend` | 8010 |
| `.env.example` 的 `FRONTEND_API_BASE_URL` | 8010 |

风险：

- 按 README 启动后端时，前端代理正常；
- 按根脚本启动后端时，后端跑在 8010，但前端仍代理到 8000；
- 用户会看到“后端已启动，但前端服务不可用 / 登录失败”。

#### 4.2 前端环境变量命名不一致

相关文件：

- `.env.example`
- `frontend/src/api/client.ts`

当前冲突：

```text
.env.example: FRONTEND_API_BASE_URL=http://localhost:8010
frontend/src/api/client.ts: import.meta.env.VITE_API_BASE_URL
```

风险：

- Vite 只暴露 `VITE_` 前缀变量；
- 用户配置 `FRONTEND_API_BASE_URL` 不会生效；
- 前端仍走空 base URL + Vite proxy，造成排查误导。

#### 4.3 前端 host 口径不统一，可能出现 `localhost` / `127.0.0.1` / `::1` 问题

相关文件：

- `frontend/vite.config.ts`
- `package.json`
- `README.md`

当前状态：

- Vite 配置只写 `port: 5173`；
- 如果启动时不显式传 `--host 127.0.0.1`，Windows 下可能监听到 IPv6 `::1`；
- 用户访问 `http://127.0.0.1:5173/login` 时会显示服务不可用。

#### 4.4 npm / pnpm 锁文件混用

相关文件：

- `pnpm-lock.yaml`
- `frontend/package-lock.json`
- `frontend/package.json`
- `README.md`
- `package.json`

当前状态：

- README 和根脚本使用 pnpm；
- 仓库同时存在 `frontend/package-lock.json`；
- 表示历史上使用过 npm；
- pnpm lock 与当前前端依赖可能不同步。

风险：

- 不同机器安装依赖结果不一致；
- CI 或新环境可能失败；
- “本机能跑，换环境不能跑”。

#### 4.5 前端 API 请求没有完全统一到 `src/api/client.ts`

相关文件：

- `frontend/src/api/client.ts`
- `frontend/src/pages/LedgerManagementPage.tsx`
- `frontend/src/pages/BasicData/ChartOfAccountsPage.tsx`
- `frontend/src/pages/BasicData/OpeningBalancesPage.tsx`
- `frontend/src/pages/BasicData/CounterpartiesPage.tsx`
- `frontend/src/pages/WorkspacePage.tsx`
- `frontend/src/pages/AgentChatPage.tsx`
- `frontend/src/pages/ProjectsPage.tsx`
- `frontend/src/pages/LedgerLifecyclePage.tsx`
- `frontend/src/pages/ImportPage.tsx`

当前状态：

- 主 client 使用 `fetch`，统一读取 `VITE_API_BASE_URL`，统一加 token；
- 但多个页面仍直接 `fetch` 或自定义 `API_BASE`；
- 存在一个疑似历史路径：`WorkspacePage.tsx` 中 `/api/auth/password`，而当前登录接口是 `/api/auth/login/password`。

风险：

- token 处理不一致；
- 401 行为不一致；
- API base URL 不一致；
- 后续改网关或端口时容易漏改；
- 出现内部通信 404 / 401 / CORS 类低级错误。

#### 4.6 后端依赖声明不完整

相关文件：

- `backend/pyproject.toml`
- `backend/app/core/security.py`
- `alembic.ini`
- `backend/alembic`

当前状态：

`backend/app/core/security.py` 使用：

```text
python-jose
passlib
bcrypt
```

但 `backend/pyproject.toml` 当前未声明这些依赖。

项目还存在 Alembic 配置和目录，但 `pyproject.toml` 未声明：

```text
alembic
```

风险：

- 新环境 `pip install -e .` 后可能启动失败；
- 登录认证依赖缺失；
- 数据库迁移命令不可用。

#### 4.7 数据库迁移机制不统一

相关文件：

- `backend/app/main.py`
- `backend/alembic`
- `alembic.ini`
- `backend/app/core/config.py`

当前状态同时存在：

- `Base.metadata.create_all(bind=engine)`；
- Alembic 目录；
- SQLite 本地 schema 补丁逻辑。

风险：

- SQLite 与 PostgreSQL 表结构可能不一致；
- 本地能跑，PostgreSQL 环境缺列；
- 财务主数据和凭证数据可能出现结构性差异。

#### 4.8 SQLite 默认路径受启动目录影响

相关文件：

- `backend/app/core/config.py`
- `README.md`
- `package.json`

当前默认：

```text
sqlite:///./finance_audit.db
```

风险：

- 从 `backend` 启动时使用 `backend/finance_audit.db`；
- 从项目根启动时可能使用根目录 `finance_audit.db`；
- 用户会误以为团队、账套、会计主体配置丢失。

#### 4.9 Qdrant 自动降级可能隐藏环境差异

相关文件：

- `backend/app/services/vector_store_service.py`
- `backend/app/core/config.py`
- `docker-compose.yml`
- `.env.example`

当前逻辑：

- 优先远程 Qdrant；
- 远程失败后降级到本地 path。

风险：

- Docker Qdrant 没启动时不会明显失败；
- 向量数据写入本地路径；
- 后续启动 Docker Qdrant 后查不到之前数据。

#### 4.10 Redis 配置存在但代码未使用

相关文件：

- `docker-compose.yml`
- `.env.example`
- `backend/app/core/config.py`

当前状态：

- Redis 服务、环境变量、配置项存在；
- 但代码中未发现实际 Redis client 使用。

风险：

- 容易让部署者误认为 Redis 是当前运行必需项；
- 但这不是当前通信故障的直接原因。

## Proposed Changes

### 1. 统一运行技术栈声明

#### 文件

- `README.md`
- `.trae/rules/project_rules.md` 或 `.trae/documents/task-governance-and-sequencing-plan.md`

#### What

明确当前项目标准技术栈：

```text
Frontend: React 18 + TypeScript + Vite 5 + Ant Design 6 + react-router-dom 7 + fetch
Backend: Python 3.11+ + FastAPI + Uvicorn + SQLAlchemy 2 + Pydantic Settings
Database: SQLite for local fallback, PostgreSQL for service mode
Vector: Qdrant
Package manager: pnpm for frontend/root scripts, pip/pyproject for backend
```

#### Why

让后续开发、排错、运行命令有统一依据，避免 npm/pnpm、端口、API base、数据库路径混乱。

#### How

在 README 和项目规则中补充“当前标准技术栈与不得混用事项”。

### 2. 统一前端包管理器为 pnpm

#### 文件

- `README.md`
- `package.json`
- `frontend/package-lock.json`
- `pnpm-lock.yaml`

#### What

明确前端和根脚本只使用 pnpm。

#### Why

避免 npm lock 与 pnpm lock 并存导致依赖树分叉。

#### How

- README 只保留 pnpm 安装与启动命令；
- 根脚本继续使用 pnpm；
- 删除或不再维护 `frontend/package-lock.json`；
- 重新生成/同步 `pnpm-lock.yaml`。

注意：删除锁文件属于执行阶段操作，计划阶段不执行。

### 3. 统一后端端口为 8000，前端端口为 5173

#### 文件

- `package.json`
- `.env.example`
- `frontend/vite.config.ts`
- `README.md`

#### What

本地开发固定为：

```text
Backend: http://127.0.0.1:8000
Frontend: http://127.0.0.1:5173
```

#### Why

当前多数文件已使用 8000；将 8010 清理掉改动最小。

#### How

- `package.json` 的 `dev:backend` 改为 `--port 8000`；
- `package.json` 的 `dev:frontend` 显式加 `--host 127.0.0.1 --port 5173`；
- `frontend/vite.config.ts` 增加 `host: '127.0.0.1'`；
- `.env.example` 使用 `VITE_API_BASE_URL=http://127.0.0.1:8000`；
- README 全部统一成 `127.0.0.1`。

### 4. 统一前端 API base 环境变量

#### 文件

- `.env.example`
- `README.md`
- `frontend/src/api/client.ts`

#### What

只使用：

```text
VITE_API_BASE_URL
```

不再宣传：

```text
FRONTEND_API_BASE_URL
```

#### Why

Vite 只暴露 `VITE_` 前缀变量。

#### How

- `.env.example` 替换变量名；
- README 解释：如果不配置，则通过 Vite proxy 走同源 `/api`；
- `client.ts` 当前无需改动。

### 5. 逐步统一前端 API 请求入口

#### 文件

- `frontend/src/api/client.ts`
- `frontend/src/pages/LedgerManagementPage.tsx`
- `frontend/src/pages/BasicData/ChartOfAccountsPage.tsx`
- `frontend/src/pages/BasicData/OpeningBalancesPage.tsx`
- `frontend/src/pages/BasicData/CounterpartiesPage.tsx`
- `frontend/src/pages/WorkspacePage.tsx`
- `frontend/src/pages/AgentChatPage.tsx`
- `frontend/src/pages/ProjectsPage.tsx`
- `frontend/src/pages/LedgerLifecyclePage.tsx`
- `frontend/src/pages/ImportPage.tsx`

#### What

将散落的直接 `fetch` 逐步收口到 `frontend/src/api/client.ts` 或至少复用 `api.baseUrl` 和统一 token 处理。

#### Why

减少内部通信路径、token、错误处理、401 行为不一致。

#### How

分阶段执行：

1. 本次公共参数治理只记录风险，不大规模改页面；
2. 优先修明显错误路径，如 `/api/auth/password`；
3. 后续每个业务域改动时，顺手把该域 API 收口，不跨域大重构。

### 6. 补齐后端 pyproject 运行依赖

#### 文件

- `backend/pyproject.toml`
- `backend/app/core/security.py`
- `alembic.ini`

#### What

将实际运行依赖加入 `backend/pyproject.toml`：

```text
python-jose
passlib[bcrypt]
alembic
```

#### Why

避免新环境安装后认证模块或迁移命令缺依赖。

#### How

- 在 dependencies 中补充依赖；
- 保持 Python 3.11+；
- 不改变认证业务逻辑。

### 7. 固定 SQLite 默认路径

#### 文件

- `backend/app/core/config.py`
- `README.md`

#### What

让默认 SQLite 数据库固定到：

```text
backend/finance_audit.db
```

#### Why

避免不同启动目录生成不同数据库文件，造成配置“看似丢失”。

#### How

- 在 `config.py` 中基于 `BACKEND_ENV_FILE` 所在目录计算后端目录；
- 默认 `database_url` 改为稳定绝对 SQLite URL；
- README 说明默认数据库位置；
- 不自动迁移已有根目录数据库文件。

### 8. 明确数据库迁移口径，但不在本任务重构迁移体系

#### 文件

- `README.md`
- `.trae/documents/task-governance-and-sequencing-plan.md`

#### What

记录当前状态：

```text
本地开发暂用 create_all + SQLite 补丁兼容；正式迁移治理另开任务处理 Alembic 统一。
```

#### Why

数据库迁移体系属于较大工程，不应混入公共参数治理任务中一次性重构。

#### How

- 只记录边界；
- 不移除 create_all；
- 不改 Alembic；
- 不改表结构。

### 9. 明确 Qdrant / Redis 当前状态

#### 文件

- `README.md`
- `.env.example`

#### What

说明：

- Qdrant 可用远程服务，也可能降级本地 path；
- Redis 目前是预留配置，不是当前必需运行依赖。

#### Why

避免把 Qdrant 或 Redis 的启动状态误判成前后端通信故障。

#### How

- README 增加“依赖服务说明”；
- 不改 Qdrant 降级逻辑；
- 不新增 Redis 使用。

## Assumptions & Decisions

1. 标准前端栈固定为 React + TypeScript + Vite + Ant Design，不切换框架。
2. 标准后端栈固定为 FastAPI + SQLAlchemy，不切换后端框架。
3. 前端包管理器统一为 pnpm，不继续维护 npm lock。
4. 后端包管理以 `backend/pyproject.toml` 为准。
5. 本地开发后端端口统一为 8000，前端端口统一为 5173。
6. 本地开发访问地址统一使用 `127.0.0.1`，减少 Windows IPv4/IPv6 差异。
7. 前端环境变量统一使用 `VITE_API_BASE_URL`。
8. 默认 SQLite 路径固定到后端目录。
9. 本计划不做业务功能变更，不做数据库迁移体系重构。

## In Scope

- 技术栈统一口径；
- npm / pnpm 包管理边界；
- 前后端端口与 host；
- API base 环境变量；
- 后端运行依赖声明；
- SQLite 默认路径；
- README 与配置文件一致性；
- Qdrant / Redis 当前运行状态说明；
- 记录前端直接 fetch 的风险清单。

## Out of Scope

- 不改登录认证业务逻辑；
- 不改账套、团队、会计主体规则；
- 不改导航 UI；
- 不改凭证、报表、审计流程；
- 不重构所有前端 API 页面；
- 不重构数据库迁移体系；
- 不迁移历史 SQLite 数据文件；
- 不新增 Redis 队列或缓存功能；
- 不改变 Qdrant 降级策略。

## Verification Steps

实施后建议验证：

### 1. 依赖安装验证

```powershell
pnpm --dir frontend install
cd backend
pip install -e .
```

确认前端不再依赖 npm lock，后端认证依赖可导入。

### 2. 启动验证

从项目根目录：

```powershell
pnpm dev:backend
pnpm dev:frontend
```

确认：

```text
http://127.0.0.1:8000/health -> 200
http://127.0.0.1:5173/login -> 200
```

### 3. API 代理验证

确认前端默认请求链路为：

```text
127.0.0.1:5173/api/* -> 127.0.0.1:8000/api/*
```

不再出现 8010。

### 4. 类型与测试验证

```powershell
pnpm --dir frontend lint
python -m pytest backend/tests
```

### 5. 数据库路径验证

确认默认 SQLite 文件路径稳定为：

```text
backend/finance_audit.db
```

不因从项目根或 backend 目录启动而切换数据库。

### 6. 边界验证

检查本任务完成后没有改动以下内容：

- 登录业务流程；
- 账套创建规则；
- 导航顺序；
- 凭证和报表计算；
- 审计测试逻辑。

## Recommended Execution Order

1. 统一 `package.json` 中前后端启动脚本。
2. 统一 `.env.example` 的 `VITE_API_BASE_URL` 和端口。
3. 统一 `frontend/vite.config.ts` host/port/proxy。
4. 补齐 `backend/pyproject.toml` 中认证和迁移运行依赖。
5. 固定 `backend/app/core/config.py` 的 SQLite 默认路径。
6. 更新 README：技术栈、启动方式、env 位置、依赖服务说明。
7. 在治理规则中增加“技术栈与公共参数变更必须独立归 D12”的边界说明。
8. 删除或处理 `frontend/package-lock.json`，统一 pnpm。
9. 运行验证命令。

## Final Recommendation

下一步建议执行任务：

```text
D12 技术栈一致性与公共参数统一
```

优先解决最容易造成内部通信错误的低级冲突：

1. 后端端口 8000 / 8010；
2. `FRONTEND_API_BASE_URL` / `VITE_API_BASE_URL`；
3. `localhost` / `127.0.0.1` / `::1`；
4. npm / pnpm 锁文件混用；
5. 后端认证依赖未声明；
6. SQLite 默认路径受启动目录影响。

执行时必须保持边界：只做技术栈和公共参数统一，不扩展任何业务功能。