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

- 创建企业/账簿导入批次。
- 上传 Excel / CSV 会计分录文件。
- 上传 PDF / TXT 原始文件并抽取文本。
- 自动解析会计分录并生成初始标签。
- 将分录和文件片段写入 Qdrant 向量库。
- 基于规则识别大额整数金额、摘要异常、期末大额交易、往来挂账、重复交易等风险。
- 前端展示导入批次、分录列表、风险列表、证据链和复核操作。
- 创建账簿时可指定会计时间线起点（`accounting_start_date`），作为该账簿期间与报表的时间基准。
- 审计模式 Step1 可选择并持久化审计范围（全量 / 按科目 / 按期间），审计测试报告按已保存范围生成。
- AI 凭证生成支持会计判断策略（合规默认 / 收入优先 / 往来优先），按单据类型生成差异化草稿分录。
- AI 凭证权责发生制暂存：单发票挂应收+收入，发票+流水走「开票挂应收 → 收款核销应收」，避免发票直连银行存款。
- 导出前凭证入账（post）流程：已复核分录入账后方可导出，导出仅包含已入账分录。
- **财务报表标准列报**：资产负债表按报表项目聚合；利润表含「本期+本年累计」；现金流量表直接法分项 + 间接法调节，识别收入直接进银行与应收回款；科目表可设置 `balance_sheet_item` / `cash_flow_item`。
- **证据云空间（P0）**：以账簿为主视图，支持拖拽上传至收件箱、手动归档到项目/期间/分类；企业自建推送见 `scripts/evidence_ingest.py` 与云空间页 curl/CLI 示例；分录可反查原件。内控待办工作台合并内控/维度/风险三类提醒，仅通知不强制阻塞。详见 [.trae/specs/evidence-cloud-and-icf-workbench/spec.md](.trae/specs/evidence-cloud-and-icf-workbench/spec.md)。

## 架构与分层文档（DDD 对照）

梳理「接口 / 应用 / 领域 / 基础设施」四层，以及 **调度 vs 引擎** 与双场景解析（A 序时簿 / B 原始资料）的代码落点：

| 文档 | 用途 |
|------|------|
| [.trae/specs/evidence-cloud-and-icf-workbench/spec.md](.trae/specs/evidence-cloud-and-icf-workbench/spec.md) | **证据云空间 × 内控待办工作台** — 多通道归档与记账前待办的产品规格 |
| [.trae/documents/development-convergence-charter.md](.trae/documents/development-convergence-charter.md) | **开发收敛章程** — 防发散、API/品牌/DDD 差距与 Sprint 准入 |
| [.trae/documents/parser-dual-scenario-strategy.md](.trae/documents/parser-dual-scenario-strategy.md) | 场景 A/B 产品总纲 |
| [.trae/documents/code-truth-status.md](.trae/documents/code-truth-status.md) | 代码真值与 L1–L6 完成度 |
| [backend/docs/engine-architecture.md](backend/docs/engine-architecture.md) | 解析 / 规则 / 向量三引擎（历史文档，已链至双场景） |
| [backend/docs/tag-vs-account-hierarchy.md](backend/docs/tag-vs-account-hierarchy.md) | **Tag 与明细科目边界** — 设计目的、动态配置与性能原则 |
| [backend/docs/bookkeeping-v1-decision-record.md](backend/docs/bookkeeping-v1-decision-record.md) | **记账 v1.0 决策记录** — 发布范围 · 先验收再修 |
| [backend/docs/fixed-asset-v1-decision-record.md](backend/docs/fixed-asset-v1-decision-record.md) | **固定资产 v1.0 决策记录** — 开发起点（当前不实现） |
| [backend/docs/fixed-asset-register-schema-draft.md](backend/docs/fixed-asset-register-schema-draft.md) | **固定资产表结构草案** — 全生命周期 Schema |

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

## 生产部署

> **首次上线**（装 Docker、配 `.env`、加 Swap 等）见 [DEPLOYMENT.md](./DEPLOYMENT.md)。  
> **代码 + 数据层统一上线**（推荐日常更新）见 [deploy/DEPLOY_SYNC.md](./deploy/DEPLOY_SYNC.md)。  
> 本节描述**已有生产环境**上的日常更新流程（解析引擎、前后端代码变更）。

### 环境信息

| 项目 | 值 |
| --- | --- |
| 服务器 | `root@47.122.117.76`（阿里云轻量 · 武汉） |
| 代码目录 | `/root/audit-platform-main` |
| Compose | `deploy/docker-compose.yml` + `deploy/.env` |
| 访问地址 | `https://47.122.117.76`（自签证书，首次需点「继续访问」） |
| SSH 密钥 | 本地 `.pem`，例如 `C:/Users/<用户名>/Desktop/xlsx/工作空间部署方案/id_banmao.pem` |

### 生产部署步骤

**1. 本地同步代码到服务器**

任选其一（改少量文件用 `scp`，大版本用 tarball）：

```powershell
# 变量（按本机路径修改）
$KEY = "C:/Users/banmao/Desktop/xlsx/工作空间部署方案/id_banmao.pem"
$HOST = "root@47.122.117.76"
$REMOTE = "/root/audit-platform-main"

# 方式 A：同步单个/多个文件（示例）
scp -i $KEY backend/app/services/doc_parsing/file_parser_service.py "${HOST}:${REMOTE}/backend/app/services/doc_parsing/"

# 方式 B：打包上传（保留 deploy/.env，勿覆盖生产密钥）
tar -czf $env:TEMP/audit-deploy.tgz --exclude=node_modules --exclude=.git --exclude=backend/.venv .
scp -i $KEY $env:TEMP/audit-deploy.tgz "${HOST}:/tmp/"
ssh -i $KEY $HOST "cd $REMOTE && cp deploy/.env /tmp/deploy.env.bak && tar -xzf /tmp/audit-deploy.tgz && cp /tmp/deploy.env.bak deploy/.env"
```

**2. 在服务器上重建并启动**

```bash
cd /root/audit-platform-main/deploy

# 解析/后端变更：必须 --no-cache，否则 Docker COPY 层可能仍用旧代码
docker compose build --no-cache backend
docker compose up -d backend

# 前端变更
docker compose build web
docker compose up -d web
```

**3. 一键脚本（解析引擎专项）**

仓库内 `deploy/prod_deploy_parser_fix.sh` 已封装：无缓存重建 backend → 容器内单元/API 回归 → 重建 web → 健康检查。

```bash
ssh -i <pem> root@47.122.117.76 "bash /root/audit-platform-main/deploy/prod_deploy_parser_fix.sh"
```

**4. 部署后浏览器**

前端静态资源有缓存：**硬刷新**（Windows：`Ctrl+F5`）后再验 UI，避免仍看到旧页面。

**5. 其他运维脚本**

| 脚本 | 用途 |
| --- | --- |
| `deploy/rebuild-slim-backend.sh` | 精简后端重建 + legacy DB 修复 + schema 校验 + 冒烟 |
| `deploy/prod_deploy_full.sh` | **推荐** 全量部署：backend + schema 审计 + web + 冒烟 |
| `deploy/apply_prod_schema.sh` | 仅数据层：fix_legacy_db + Alembic upgrade + 全量审计 |
| `deploy/migrate_to_alembic.sh` | 一次性：legacy 库 stamp 到 Alembic head |
| `deploy/sync_and_deploy.ps1` | Windows 一键：打包上传 + `prod_deploy_full.sh` |
| `deploy/DEPLOY_SYNC.md` | 代码与数据层一致性说明与检查清单 |
| `deploy/prod_health_report.sh` | 汇总容器日志 500、缺列、API 探测 |
| `deploy/server-cleanup.sh` | 清理 `/tmp` 与仓库内测试残留（不动 Docker 卷） |

### 解析引擎回归验证

解析相关改动上线后，在**已运行的 backend 容器内**执行（脚本路径 `/app/backend/scripts/`，由镜像 `COPY backend/` 带入）。

**单元级（直接调 `parse_structured_accounting_entries`）**

```bash
docker exec deploy-backend-1 python /app/backend/scripts/prod_regression_daybook.py
```

- 必测样本：`backend/test_daybook.csv`（`entries > 0` 为通过）
- 可选：`--extra /path/to/your.xlsx` 追加自定义文件
- 退出码 `0` 为通过

**API 端到端（登录 → 创建 import-job → 上传 CSV → sync 处理）**

```bash
docker exec deploy-backend-1 python /app/backend/scripts/prod_api_regression_daybook.py
```

- 检查输出 JSON 中 `total_entries > 0`
- 依赖容器内 `http://127.0.0.1:8000` 与 SQLite 生产库（会写入测试组织/批次）

**与 D05 策略的关系**：序时簿/凭证 Excel 属场景 A（电子档案），验收口径见 [.trae/documents/parser-dual-scenario-strategy.md](./.trae/documents/parser-dual-scenario-strategy.md) TOP3 序时账条目。

### 常见问题

**改了代码但容器里仍是旧逻辑（Docker COPY 缓存）**

- `backend.Dockerfile` 使用 `COPY backend/ ./backend/`，BuildKit 可能复用未失效的 COPY 层。
- **处理**：后端/解析变更务必 `docker compose build --no-cache backend`，不要只 `up -d --build`。
- 新增 `backend/scripts/*.py` 同样必须先同步到服务器再 build，否则 `docker exec … python /app/backend/scripts/xxx.py` 会报找不到文件。

**回归脚本路径**

- 容器内工作目录为 `/app`；脚本在 `/app/backend/scripts/`。
- `prod_regression_daybook.py` 用 `Path(__file__).parents[1]` 定位 `backend/`，样本 `test_daybook.csv` 必须在镜像内存在。

**`AI_BASE_URL` 留空**

- `deploy/.env` 中 `AI_BASE_URL` / `AI_API_KEY` / `AI_MODEL` **可全部留空**；核心审计、序时簿解析、规则风险不依赖大模型。
- 留空时系统自动降级为规则/模板；需要 AI 凭证再按 [DEPLOYMENT.md 第九节](./DEPLOYMENT.md) 填写并 `up -d` 重启。

**前端已部署但界面未变**

- 浏览器强缓存静态 JS/CSS：部署 web 后 **Ctrl+F5**（或无痕窗口）再测。
- 确认 web 容器已重建：`docker compose -f deploy/docker-compose.yml ps`。

**2GB 内存 build 失败（OOM）**

- 见 [DEPLOYMENT.md 四·补充](./DEPLOYMENT.md)：先加 4GB Swap，**串行** `build backend` 再 `build web`，不要并行构建。

**数据库与配置**

- 生产数据在 Docker 卷 `deploy_app_data`（库文件 `/data/finance_audit.db`），重建镜像/容器**不会**丢数据。
- 切勿用 tarball 覆盖服务器上的 `deploy/.env`（含 `SECRET_KEY`）；同步前备份见上文步骤。

## 项目文档（以代码为准）

**状态真值**（完成度、待办、L 级）：

- [.trae/documents/code-truth-status.md](./.trae/documents/code-truth-status.md) — ★ 唯一真值来源（随 `main` 更新）

**治理与约束**：

- [AGENTS.md](./AGENTS.md) — 财务规则、API 原则、任务顺序
- [.trae/documents/parser-dual-scenario-strategy.md](./.trae/documents/parser-dual-scenario-strategy.md) — D05 解析双场景总纲（A 电子档案 / B 实体化）
- [.trae/specs/document-parsing-engine/spec.md](./.trae/specs/document-parsing-engine/spec.md) — 解析引擎 spec（TOP3 + 修正回流）
- [.trae/documents/api-boundary-governance-plan.md](./.trae/documents/api-boundary-governance-plan.md) — API 收敛细则
- [.trae/documents/current-risks-and-tasks.md](./.trae/documents/current-risks-and-tasks.md) — 风险与 Sprint 摘要
- [.trae/documents/requirements-domain-index.md](./.trae/documents/requirements-domain-index.md) — 需求域 D01–D13

历史 roadmap / spec checklist **不得**单独作为「已完成」依据，须对照 code-truth-status。

## 变更记录与 Agent 集成

- [CHANGELOG.md](./CHANGELOG.md) — 重要功能修复与合并说明
- [CURSOR_GITHUB_SETUP.md](./CURSOR_GITHUB_SETUP.md) — Cursor Cloud Agent 连接 GitHub、创建 PR 的逐步配置
- [AUTOMATIONS_SETUP.md](./AUTOMATIONS_SETUP.md) — 定时测试、Issue 自动开发、PR 合并更新文档

### 对话式 Agent 助手（鉴权 + Tool 调用）

在 **Agent 助手** 页面（`/agent`）可通过自然语言直接完成查询类工作，无需跳转业务页面：

| 能力 | 说明 |
|------|------|
| 鉴权 | 沿用 JWT + `X-Ledger-Id`（与全站账簿上下文一致） |
| API | `POST /api/agent/assist` — 规划并自动执行低风险只读工具 |
| 模型 | 优先读取 **解析引擎配置**（DB）；未配置时回退 `.env`；支持 Ollama 本地与 OpenAI 兼容云端 |
| 工具 | 科目表、往来、会计期间、证据收件箱、导入任务、试算平衡、内控待办等（白名单） |
| 风控 | 低风险自动执行；中高风险仅列入 `pending_actions`，不阻塞对话 |

**配置大模型**：菜单 → 解析引擎配置（`/parser-engine/config`），与文档解析共用同一套 AI 连接参数。

**示例对话**：「列出科目表」「查看证据收件箱」「有哪些导入任务」「内控待办有哪些」
