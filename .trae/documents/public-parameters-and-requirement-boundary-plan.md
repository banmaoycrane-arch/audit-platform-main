# 公共参数与需求边界治理计划

## Summary

本计划用于回顾当前项目原定计划与现有需求治理规则，重点识别“通讯端口、启动进程、环境变量、SQLite 数据库路径”等项目公共参数是否边界清晰，避免后续开发偏离业务需求，或因为端口/进程口径不一致导致误判为业务 bug。

本计划只治理公共参数和任务边界，不改变任何业务功能。

## Current State Analysis

### 1. 角色与工作方式

依据 `.trae/rules/project_rules.md`：

- 用户是专业会计师、项目决策者、编程初学者。
- AI 是技术实现者、编程知识补充者、财务视角翻译者。
- 后续任务必须先识别需求归属域 D01-D13，确认 Owner Spec，并写清 In Scope / Out of Scope。

这意味着：

- 业务需求应以财务实务为主线；
- 技术参数如端口、进程、环境变量属于公共工程约束；
- 公共参数问题可以修，但不能借机扩展业务功能。

### 2. 原定计划与当前主线

现有治理文档显示，当前可信依据应优先使用：

- `.trae/documents/requirements-domain-index.md`
- `.trae/documents/requirements-boundary-governance-plan.md`
- `.trae/documents/core-business-concepts-boundary.md`
- `.trae/documents/task-governance-and-sequencing-plan.md`
- `.trae/rules/project_rules.md`

早期文档如 `.trae/documents/finance-vector-audit-plan.md`、`.trae/documents/workspace-recap-and-next-step.md` 可作为历史参考，但其中“当前代码状态”“spec 数量”“完成度”等信息可能已经过期。

当前需求治理原则是：

```text
阻塞 bug → 上下文和主数据边界 → 记账闭环 → 审计闭环 → AI/EntryTag/向量增强 → 银行/税务/固定资产/进销存扩展
```

### 3. 当前公共参数冲突点

#### 3.1 后端端口 8000 与 8010 不一致

相关文件：

- `README.md`
- `package.json`
- `frontend/vite.config.ts`
- `.env.example`
- `.trae/specs/fix-register-and-backend-availability/spec.md`

当前状态：

| 来源 | 后端端口 |
|---|---:|
| README 后端启动说明 | 8000 |
| README 健康检查 | 8000 |
| Vite proxy | 8000 |
| fix-register-and-backend-availability spec | 8000 |
| 根 `package.json` 的 `dev:backend` | 8010 |
| `.env.example` 的 `FRONTEND_API_BASE_URL` | 8010 |

风险：

- 如果后端按根脚本启动到 8010，前端代理仍请求 8000；
- 如果前端访问 `/api`，会出现服务不可用或登录失败；
- 这类问题容易被误判为登录、账套、权限、dashboard 等业务 bug。

#### 3.2 前端环境变量命名不一致

相关文件：

- `.env.example`
- `frontend/src/api/client.ts`

当前状态：

- `.env.example` 写的是 `FRONTEND_API_BASE_URL`；
- 前端实际读取的是 `VITE_API_BASE_URL`。

风险：

- 用户按 `.env.example` 配置后，前端不会读取；
- Vite 只暴露 `VITE_` 前缀变量；
- 最终仍依赖 Vite proxy，导致排查链路不清晰。

#### 3.3 前端监听地址可能出现 `localhost`、`127.0.0.1`、`::1` 不一致

相关文件：

- `frontend/vite.config.ts`
- README 启动说明
- 实际启动命令

当前状态：

- Vite 配置只指定 `port: 5173`；
- 如果未显式传 `--host 127.0.0.1`，本机可能监听到 `localhost` 或 IPv6 `::1`；
- 用户访问 `http://127.0.0.1:5173/login` 时可能显示服务不可用。

风险：

- 服务实际启动但访问地址不匹配；
- 重复出现“服务不可用”；
- 影响登录、工作台、账套配置等验收。

#### 3.4 SQLite 相对路径受启动目录影响

相关文件：

- `backend/app/core/config.py`
- README 后端启动说明
- 根 `package.json`

当前配置：

```text
sqlite:///./finance_audit.db
```

风险：

- 如果从 `backend` 目录启动，数据库文件倾向于 `backend/finance_audit.db`；
- 如果从项目根启动，数据库文件可能变成根目录 `finance_audit.db`；
- 这会导致“同一账号登录后团队、账套、主体配置像丢失了一样”，实质上可能是连接了不同 SQLite 文件。

#### 3.5 后端 `.env` 读取位置与 README 表述不够清晰

相关文件：

- `backend/app/core/config.py`
- `.env.example`
- `backend/.env`
- README

当前状态：

`backend/app/core/config.py` 明确读取：

```text
backend/.env
```

但 README 只说复制 `.env.example` 为 `.env`，没有明确应该复制到根目录还是 `backend/.env`。

风险：

- 用户把 `.env` 放在根目录，后端不读取；
- `SECRET_KEY`、`DATABASE_URL` 等关键配置失效；
- 登录、Token、数据库连接可能被误判为业务问题。

## Proposed Changes

### 1. 统一本地开发端口，以 8000 作为后端开发端口

#### 文件

- `package.json`
- `.env.example`
- `README.md`
- `frontend/vite.config.ts`

#### What

将本地开发默认后端端口统一为：

```text
127.0.0.1:8000
```

前端端口统一为：

```text
127.0.0.1:5173
```

#### Why

当前多数文件已经使用 8000：README、Vite proxy、健康检查 spec。统一到 8000 改动最小，且符合 Uvicorn 默认端口。

#### How

- 将根 `package.json` 中 `dev:backend` 的 `--port 8010` 改为 `--port 8000`；
- 将 `.env.example` 中后端 API 示例从 8010 调整为 8000；
- README 中明确推荐访问 `http://127.0.0.1:5173` 和 `http://127.0.0.1:8000/health`；
- 保持 `frontend/vite.config.ts` 代理到 `http://127.0.0.1:8000`。

### 2. 统一前端 API 环境变量名称为 `VITE_API_BASE_URL`

#### 文件

- `.env.example`
- `README.md`
- `frontend/src/api/client.ts`

#### What

确认前端只使用：

```text
VITE_API_BASE_URL
```

不再使用或宣传：

```text
FRONTEND_API_BASE_URL
```

#### Why

Vite 前端只能读取 `VITE_` 前缀变量。保留错误名称会误导配置。

#### How

- `.env.example` 将 `FRONTEND_API_BASE_URL` 改为 `VITE_API_BASE_URL`；
- README 补充说明：未配置 `VITE_API_BASE_URL` 时，前端通过 Vite proxy 请求同源 `/api`；
- `frontend/src/api/client.ts` 当前已读取 `VITE_API_BASE_URL`，原则上不需要改业务逻辑。

### 3. 明确启动命令，避免 `localhost` / `127.0.0.1` / `::1` 混用

#### 文件

- `package.json`
- `frontend/vite.config.ts`
- `README.md`

#### What

本地开发统一用：

```powershell
pnpm dev:backend
pnpm dev:frontend
```

其中：

```text
后端：127.0.0.1:8000
前端：127.0.0.1:5173
```

#### Why

避免 Vite 只监听 IPv6 `::1`，用户访问 `127.0.0.1` 时显示服务不可用。

#### How

- 将根 `package.json` 的 `dev:frontend` 调整为显式传参：`pnpm --dir frontend dev -- --host 127.0.0.1 --port 5173`；
- README 统一写 `127.0.0.1`，不再混用 `localhost`；
- 可选：在 `frontend/vite.config.ts` 中添加 `host: '127.0.0.1'`，作为配置层兜底。

### 4. 固定 SQLite 默认数据库路径，避免启动目录影响数据文件

#### 文件

- `backend/app/core/config.py`
- `README.md`

#### What

将 SQLite 默认路径从相对当前工作目录改为相对后端目录的稳定路径。

建议默认仍使用：

```text
backend/finance_audit.db
```

#### Why

同一项目从不同目录启动不应产生两个数据库文件。否则用户会看到“团队、账套、会计主体配置丢失”。

#### How

- 在 `backend/app/core/config.py` 中基于 `Path(__file__).resolve().parents[2]` 生成后端目录；
- 默认 `database_url` 使用稳定绝对 SQLite URL；
- README 说明默认 SQLite 文件位置；
- 不改已有数据库结构，不迁移业务数据，除非后续用户明确要求。

### 5. 明确后端 `.env` 文件位置

#### 文件

- `README.md`
- `.env.example`
- `backend/app/core/config.py`

#### What

文档明确：

```text
后端实际读取 backend/.env
```

#### Why

避免用户将 `.env` 放到项目根目录但后端未读取。

#### How

- README 环境变量章节改为：复制 `.env.example` 到 `backend/.env`；
- `.env.example` 保留在根目录作为模板；
- 不在前端暴露后端敏感配置。

### 6. 新增“公共参数边界规则”到项目规则或治理文档

#### 文件

- `.trae/rules/project_rules.md`
- 或 `.trae/documents/task-governance-and-sequencing-plan.md`

#### What

增加公共参数规则：

```text
公共参数属于 D12 环境诊断 / 工程治理，不得混入业务需求。
端口、启动命令、环境变量、数据库路径、进程管理变更必须独立说明 In Scope / Out of Scope。
```

#### Why

防止未来修一个登录问题时又改导航、dashboard、账套规则；也防止修一个端口问题时误改认证逻辑。

#### How

- 只新增一小段规则；
- 不改变 D01-D13 现有分类；
- 将本次公共参数治理归为：

```text
Domain: D12 - 缺陷修复与环境诊断
Status: engineering-governance
Owner Spec: fix-register-and-backend-availability 或新增轻量文档 public-parameters-and-process-boundary
```

## Assumptions & Decisions

1. 后端开发端口统一为 `8000`，因为 README、Vite proxy、健康检查 spec 已主要采用 8000。
2. 前端开发端口统一为 `5173`。
3. 本地开发推荐统一使用 `127.0.0.1`，减少 Windows 下 `localhost`、IPv4、IPv6 差异。
4. 前端 API 环境变量统一为 `VITE_API_BASE_URL`。
5. 后端 `.env` 文件位置统一为 `backend/.env`。
6. 默认 SQLite 数据库固定为 `backend/finance_audit.db`。
7. 本计划不处理登录业务、不处理账套业务、不处理导航 UI、不处理报表或审计逻辑。
8. 如果用户已有根目录 `finance_audit.db`，是否迁移数据需单独确认，不在本计划默认范围内。

## In Scope

- 端口统一：8000 / 5173；
- 启动脚本统一；
- Vite proxy 与后端端口一致；
- 前端环境变量命名统一；
- 后端 `.env` 位置说明统一；
- SQLite 默认路径稳定化；
- 公共参数治理规则补充；
- README 与配置口径统一。

## Out of Scope

- 不修改认证业务逻辑；
- 不修改账套、团队、会计主体业务规则；
- 不修改导航顺序；
- 不新增凭证、报表、审计、AI 功能；
- 不迁移历史数据库文件，除非用户单独确认；
- 不引入新的进程管理工具；
- 不改 Docker Compose 服务端口，除非后续发现明确冲突。

## Verification Steps

实施后建议验证：

### 1. 配置一致性检查

检查以下文件口径一致：

- `package.json`
- `.env.example`
- `README.md`
- `frontend/vite.config.ts`
- `frontend/src/api/client.ts`
- `backend/app/core/config.py`

确认：

```text
前端端口：5173
后端端口：8000
前端环境变量：VITE_API_BASE_URL
后端 env：backend/.env
SQLite 默认路径：backend/finance_audit.db
```

### 2. 启动验证

从项目根目录执行：

```powershell
pnpm dev:backend
pnpm dev:frontend
```

或分别执行等价命令。

验证：

```text
http://127.0.0.1:8000/health 返回 200
http://127.0.0.1:5173/login 返回 200
```

### 3. API 代理验证

访问前端后，登录或调用 `/api` 接口时，应走：

```text
127.0.0.1:5173/api/* -> 127.0.0.1:8000/api/*
```

不应再出现前端请求 8010 或服务不可用。

### 4. 数据库路径验证

确认后端启动后只使用：

```text
backend/finance_audit.db
```

不再因为启动目录不同生成根目录 `finance_audit.db`。

### 5. 边界验证

本任务完成后，不应出现以下变更：

- 登录接口逻辑变化；
- 账套创建业务规则变化；
- 导航菜单变化；
- 报表计算变化；
- 审计流程变化。

## Recommended Execution Order

1. 修改根 `package.json` 启动脚本，统一端口与 host。
2. 修改 `.env.example`，统一 `VITE_API_BASE_URL` 与 8000。
3. 修改 README，明确 `127.0.0.1`、`backend/.env`、SQLite 默认路径。
4. 可选修改 `frontend/vite.config.ts`，增加 `host: '127.0.0.1'` 兜底。
5. 修改 `backend/app/core/config.py`，固定 SQLite 默认路径。
6. 补充公共参数边界规则到 `.trae/rules/project_rules.md` 或治理文档。
7. 启动前后端并验证 5173 / 8000。
8. 运行前端 lint 和必要后端测试。

## Final Recommendation

建议下一步执行本计划，任务名称为：

```text
D12 公共参数与进程边界统一
```

它是工程治理任务，不是业务功能任务。完成后，可以减少“服务不可用”“登录异常”“配置丢失”等问题中由端口、进程、环境变量、SQLite 路径造成的误判。