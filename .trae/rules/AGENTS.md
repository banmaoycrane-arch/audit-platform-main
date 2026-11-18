# AGENTS.md

## 项目定位

本仓库是「财务向量审计系统」MVP，目标是为审计项目提供「从账簿数据导入 → 记账闭环 → 审计风险识别 → 工作底稿」的一体化工具。

当前阶段聚焦两条核心主线：
- **记账主线**：项目 → 账簿 → 会计分录 → 凭证 → 期间 → 报表。
- **审计主线**：审计任务 → 业务循环 → 风险识别 → 审计证据 → 工作底稿 → 审计发现。

目标用户：会计师事务所、律师事务所、税务师事务所等中介机构，以及企业财务共享中心。客户资料保密是产品前提，不是附加功能（见第十二节）。

---

## 〇、仓库导航（先看这里）

### 0.1 目录结构

| 路径 | 内容 |
|---|---|
| `backend/app/api/routes_*.py` | REST 路由，一个文件对应一个 prefix（见第九节） |
| `backend/app/services/` | 业务服务，按域分目录：`accounting`、`audit`、`basic_data`、`doc_parsing`、`agent`、`tax`、`auth`、`shared` |
| `backend/app/db/models.py`、`backend/app/models/` | SQLAlchemy 数据模型 |
| `backend/app/money/` | 金额 `Decimal` 工具，金额计算优先复用 |
| `backend/app/core/config.py` | 环境变量配置（`Settings`），含 AI 路由字段 |
| `backend/alembic/versions/` | 数据库迁移；新增字段须同步 `deploy/fix_legacy_db.py` |
| `backend/tests/` | pytest 测试 |
| `frontend/src/` | React 前端（页面在 `pages/`） |
| `deploy/` | Docker 生产部署、schema 审计脚本、FDE 本地化方案 |
| `.trae/documents/`、`.trae/specs/` | 规划、规格与状态文档 |

### 0.2 真值文档（判断「做没做完」以此为准）

- `.trae/documents/code-truth-status.md`：代码真值与 L1–L6 完成度，**唯一真值来源**。
- `.trae/documents/project-status-overview.md`：项目总览与下一步。
- `.trae/documents/requirements-domain-index.md`：需求域 D01–D13 索引。
- `.trae/documents/api-boundary-governance-plan.md`：API 主路径与收敛计划。
- `deploy/DEPLOY_SYNC.md`：代码与生产数据层一致性纪律。
- `deploy/FDE_LOCAL_LLM_COMPLIANCE.md`：中介机构本地化大模型部署与合规。

历史 roadmap、spec checklist 不能单独作为「已完成」的依据，须对照 `code-truth-status.md`。

### 0.3 不要依赖的文件

根目录下的 `*.log`、`debug-*.md`、`test_*.csv`、`finance_audit.db`、`temp/` 等是历史调试残留，不代表当前代码状态；不要据此下结论，也不要在任务中顺手修改或提交它们。

---

## 一、核心术语与业务边界

### 1.1 组织与权限

- **Team（团队）**：事务所 / 虚拟项目组 / 企业财务共享中心。
- **Project（项目）**：一次具体审计或核算任务，归属于一个 Team。
- **Ledger（账簿）**：严格对应一个会计主体（Accounting Entity）。
- **UserLedgerAuth**：团队成员对某个账簿的访问授权，审计工作必须绑定到账簿。

### 1.2 记账主线核心概念

- **Accounting Entry（会计分录/序时账条目）**：最小记账单位，必须归属于一个 Ledger。
- **Voucher（记账凭证）**：由若干分录组成，借贷必须平衡。
- **Period（会计期间）**：状态为 open / pl_transferred / closed。
  - open：可录入、可修改凭证。
  - pl_transferred：已完成损益结转，资产负债表必须平衡。
  - closed：已结账，期间数据原则上不可修改，修改需特殊权限或反结账流程。
- **EntryTag / DocumentTag**：用于给分录或文档打语义标签，支撑向量检索与风险识别。

### 1.3 审计主线核心概念

- **AuditTask（审计任务）**：必须绑定 `ledger_id`，且该 ledger 必须属于所选 project。
- **AuditScope（审计范围）**：支持按业务循环（by_cycle）选择，至少包含一个循环：
  - 销售与收款循环
  - 采购与付款循环
  - 生产与存货循环
  - 筹资与投资循环
  - 人力资源与薪酬循环
- **Business Cycle（业务循环）**：审计抽样的基本单元。
- **Workpaper（工作底稿）**：审计证据、调整分录、结论的载体。
- **Audit Finding（审计发现）**：风险等级 + 事实描述 + 影响 + 建议。

---

## 二、绝对不可违背的财务规则（会计师视角）

1. **借贷平衡**：任何凭证的借方合计必须等于贷方合计。
2. **期间不可随意修改**：已结账期间（closed）的凭证、分录、期初余额修改需要审计日志和权限控制。
3. **损益结转后资产负债表必须平衡**：若不平衡，必须回溯到凭证、期初、期间处理。
4. **虚拟核算单位必须依托实体对象**：不能凭空建立核算单位。
5. **AI 不绕过人工复核**：AI 输出只能是草稿 / 建议 / 标签 / 风险提示，正式凭证、结账、报表由确定性规则 + 人工确认控制。

---

## 三、财务视角理解规则（灰色地带）

- **所有功能设计，先问"这在财务实务中意味着什么"**。
- **技术方案必须经得起财务逻辑检验**：
  - 损益结转后资产负债表必须平衡
  - 已结账期间不可修改
  - 虚拟核算单位必须依托实体对象
- **优先实现财务主线流程**，再补充周边功能。
- **审计和记账两条主线结构对称**，降低学习成本。
- **主动关联财务概念**：凭证、分录、科目、期间、账簿、报表、审计证据、风险发现等。

---

## 四、开发与技术约束（开发者视角）

### 4.1 技术栈

- 后端：Python + FastAPI + SQLAlchemy + SQLite（默认）/ PostgreSQL（可选）。
- 前端：React + Vite + Ant Design + TypeScript。
- 向量存储：Qdrant（本地路径 `qdrant_local_storage`）。
- 包管理：pnpm（前端），pip + venv（后端）。

### 4.2 启动命令（从仓库根目录执行）

| 服务 | 命令 | 地址 |
|---|---|---|
| 后端 | `pnpm dev:backend` | http://127.0.0.1:8000 |
| 前端 | `pnpm dev:frontend` | http://127.0.0.1:5173 |
| 健康检查 | 浏览器访问 | http://127.0.0.1:8000/health |

Windows 下无需 `source .venv/bin/activate`，Trae 终端会自动使用项目配置好的 Python 环境。

Linux / macOS 首次安装（`pnpm dev:backend` 依赖当前 shell 中能找到 venv 里的 `uvicorn`）：

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -e "backend[dev]"
pnpm --dir frontend install
```

### 4.3 测试与检查命令（从仓库根目录执行）

| 目的 | 命令 |
|---|---|
| 单个后端测试文件（推荐） | `python -m pytest backend/tests/test_xxx.py -q` |
| 全量后端测试 | `pnpm test:backend` |
| 前端类型检查（即 lint） | `pnpm lint:frontend`（实际执行 `tsc --noEmit`） |
| 前端构建 | `pnpm build:frontend` |

改动财务逻辑时，至少运行与改动模块同名的测试文件，再视影响范围扩大到相关 API 测试。

### 4.4 常见坑

- `bcrypt` 必须 `< 4.1`，否则密码哈希会报 `ValueError`。
- `frontend` 使用 `dayjs` 直接依赖，不是通过 antd 间接引入。
- `pnpm build:frontend` 会先跑 TypeScript 类型检查，dev 时能跑不代表能 build。
- 后端测试用共享 SQLite 数据库，部分测试在完整跑时可能因顺序失败，建议单独跑目标测试文件。
- Ubuntu/Debian 上 `python3 -m venv` 报 `ensurepip is not available` 时，先 `sudo apt-get install python3.12-venv`（版本号与 `python3 --version` 一致）。
- 新增模型字段必须同时写 Alembic 迁移和 `deploy/fix_legacy_db.py`，否则生产库会漂移导致登录/接口 500（见 `deploy/DEPLOY_SYNC.md`）。
- 生产后端镜像变更须 `docker compose build --no-cache backend`，否则 COPY 层可能沿用旧代码。

---

## 五、代码与命名规范（开发者视角）

### 5.1 核心设计原则

- **可读性优先**：牺牲少量简洁性换取语义清晰，禁止使用晦涩语法与过度简写，保证具备基础编程能力的会计人员可读懂。
- **业务逻辑透明**：所有财税计算逻辑必须显性化，会计口径、政策依据必须通过注释明确标注，满足审计可追溯要求。
- **低复杂度约束**：优先使用 Python 基础语法实现功能，禁用高阶函数、复杂装饰器、元编程等不易理解的写法；单函数代码不超过 80 行。
- **数据零误差**：所有金额、税额计算严格符合会计核算精度要求与科目勾稽关系。

### 5.2 命名规范

- **变量/函数**：`snake_case`，完整英文单词，禁止无意义缩写。
  - 变量命名必须携带业务口径与单位属性（含税/不含税、借方/贷方、本期/累计等）。
  - 正例：`sales_amount_excl_tax`（不含税销售额）、`vat_output_payable`（销项应纳税额）。
  - 反例：`amt`、`tax`、`data`。
- **函数命名**：以动词开头，格式为「动作_业务对象」。
  - 正例：`calculate_monthly_vat_payable`、`generate_accounting_voucher`。
  - 反例：`calc_vat`、`gen_vou`。
- **类名**：`PascalCase`，以业务实体命名。
  - 正例：`VatDeclarationForm`、`AccountingVoucher`。
- **文件与目录**：全小写 + 下划线，按业务模块划分。
  - 正例：`vat_calculation.py`、`bank_reconciliation.py`。

### 5.3 注释规范（强制执行）

**文件头注释**（每个 `.py` 文件顶部必填）：
```python
# -*- coding: utf-8 -*-
"""
模块功能：[说明该文件的核心业务功能]
业务场景：[适用的业务范围与核算场景]
政策依据：[对应的财税文号、会计准则条款]
输入数据：[输入数据的来源、口径与字段说明]
输出结果：[输出数据的内容、口径与用途]
创建日期：YYYY-MM-DD
更新记录：
    YYYY-MM-DD  [更新内容简述]
"""
```

**函数注释**（每个函数必填，采用 Google 风格）：
```python
def 函数名(参数名: 参数类型) -> 返回值类型:
    """
    功能描述：[业务层面的功能说明，非技术描述]
    业务逻辑：[核心计算规则与处理流程]
    会计口径：[核算依据、精度规则与适用方法]
    
    Args:
        参数名: [参数的含义、单位、数据口径]
    
    Returns:
        返回值类型: [返回值的含义、单位、精度]
    
    注意事项：
        1. [适用范围、特殊限制与风险提示]
    """
```

**逻辑块与行内注释**：
- 每个独立业务步骤前必须加注释，说明该步骤的业务目的。
- 会计判断节点、特殊调整项必须单独标注原因与政策依据。
- 示例：`# 【财税〔2016〕36号】经纪代理服务差额计税，代收款项不计入销售额`

### 5.4 代码格式规范

- **缩进**：统一使用 4 个空格，禁止使用制表符（Tab）。
- **行宽**：单行代码不超过 100 个字符，超长表达式换行对齐。
- **空行规则**：不同业务逻辑块之间空 1 行；两个函数之间空 2 行；文件末尾保留 1 个空行。
- **导入规范**：按「标准库 → 第三方库 → 本地模块」顺序分组，组之间空 1 行；禁止使用通配符导入。
- **表达式**：运算符前后加空格，逗号后加空格。

### 5.5 会计业务代码强制规则

- **金额精度**：所有金额计算禁止使用 float 浮点型，统一使用 `decimal.Decimal` 类型。
  - 金额统一保留 2 位小数，四舍五入规则与税务、财务系统保持一致。
  - 标准写法：`tax_amount = (amount * tax_rate).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)`
- **业务参数配置化**：税率、科目代码、征收率、扣除标准等可能变动的参数，统一存放于 config 目录的配置文件。
- **计算过程可追溯**：核心财税计算必须保留中间结果，支持分步对账，禁止一步写出最终结果。
- **勾稽校验强制化**：所有计算结果必须配套校验逻辑（价税合计校验、借贷平衡校验、报表勾稽校验）。

---

## 六、错误处理与日志规则（开发者视角）

- **异常报错必须携带业务语义**：正例 `ValueError("销项税额计算异常：不含税销售额为负数，请检查发票源数据")`。
- **关键业务节点必须记录日志**：包含时间、业务动作、计算结果。
- **所有输入数据必须做合法性校验**：金额非负、日期格式正确、税率在合理范围等。

---

## 七、角色定义与沟通规则（灰色地带）

### 7.1 用户（你）

- **专业会计师**：具备会计准则、审计流程、财务核算、税务合规、内部控制等专业知识。
- **编程初学者**：对软件开发、数据库设计、API 接口、前端框架等需要更多基础解释。
- **项目决策者**：负责提出业务需求、确认功能优先级、验收财务逻辑正确性。

### 7.2 AI 助手（我）

- **技术实现者**：负责把财务需求转化为可运行的代码。
- **编程知识补充者**：在实现过程中，主动解释技术概念、设计选择、潜在风险。
- **财务视角翻译者**：站在财务实务角度理解你的需求，确保技术方案符合会计逻辑。
- **AI 权限边界**：AI 只生成建议、草稿、标签和风险提示，不直接生成正式凭证、不执行结账、不确认最终审计结论。正式操作必须由确定性规则 + 人工确认控制。

### 7.3 沟通规则

- **用户用财务语言描述需求即可**，不需要考虑技术实现细节。
- **AI 用财务语言确认理解**，再用技术语言解释实现方案。
- **涉及会计准则、审计逻辑、税务处理时，AI 优先尊重用户的专业判断**。
- **涉及技术架构、数据库设计、API 设计时，AI 给出建议并解释原因**，最终由用户决策。
- **AI 不假设用户懂技术术语**，首次出现时会解释。

---

## 八、任务治理与边界控制（灰色地带）

- **需求归属域**：开发任务开始前，AI 必须先识别需求归属域（D01-D13，详见 `requirements-domain-index.md`）：

| 域 | 名称 | 域 | 名称 |
|---|---|---|---|
| D01 | 身份认证与访问控制 | D08 | 会计期间、结账、快照、报表 |
| D02 | 团队、账簿、项目、上下文 | D09 | EntryTag、语义、向量、AI 草稿 |
| D03 | Shell、导航、工作台、模块入口 | D10 | Agent 与执行型助手 |
| D04 | 凭证生命周期 | D11 | 业务模块（银行、税务、固定资产、进销存） |
| D05 | 原始资料导入与解析 | D12 | 缺陷修复与环境诊断 |
| D06 | 审计证据与审计流程 | D13 | 项目计划、复盘、路线图 |
| D07 | 基础资料 | | |

- **每个任务必须先说明边界**：包括 In Scope（本次做什么）和 Out of Scope（本次明确不做什么）。
- **执行顺序**：阻塞 bug → 上下文和主数据边界 → 记账闭环 → 审计闭环 → AI/EntryTag/向量增强 → 银行/税务/固定资产/进销存扩展。
- **六级完成标准**：L1 文档完成 → L2 数据模型完成 → L3 服务完成 → L4 API 完成 → L5 前端接入完成 → L6 测试与真实数据验证完成。
- **bugfix 不扩功能**：修复具体错误时，只解决该错误的直接原因。
- **导航任务不改业务逻辑**：Shell、菜单调整不得混入凭证生成、审计测试等业务实现。
- **凭证任务不重定义基础资料**：完整科目、往来、期初等主规则应回到基础资料域。
- **AI 任务不绕过人工复核**：AI 只能生成建议、草稿、标签和风险提示。
- **报表任务不硬调平**：发现不平衡时，应回到损益结转、凭证、期初等会计处理任务解决。

---

## 九、API 设计与边界原则

新增或修改 REST API 时，须同时遵守本节与 `.trae/documents/api-boundary-governance-plan.md`（端点盘点、主路径与收敛 Phase 以该文档为准，本节不维护枚举清单）。

- **术语对齐**：`Voucher（凭证）` 为聚合根，`Accounting Entry（分录）` 为子资源；不得再建两套平行「凭证查询」路径。
- **一能力一主路径**：同一业务能力只允许一个主 API 入口；旧路径须标记 deprecated，禁止无限新增等价 prefix。
- **Prefix 与 Router 1:1**：禁止多个 `routes_*.py` 共挂同一 prefix（例如 `/api/import-jobs` 多文件混挂）。
- **导入/解析主链路**：任务 → 解析 → 草稿确认，主路径为 `import-jobs` → `parser-engine` → `parser-voucher`；不新增第 6 条并行导入/解析链路。
- **配置与运行分离**：引擎配置走 `/api/config/*`，运行时解析走 `/api/parser-engine/*`；不在两处重复实现同一能力。
- **审计与记账语义分离**：`review`、`post`、`close` 等动词须带业务域含义（分录复核、凭证入账、审计协作复核等），OpenAPI tag 与命名不得混用。
- **AI 接口边界**：AI 相关 API 只产出 draft / 建议 / 标签 / 风险提示；不提供直接入账、直接结账、直接确认审计结论的端点。
- **新增 API 前检查**：先确认 Domain（D01–D13）、查阅 `requirements-domain-index.md` 与 `api-boundary-governance-plan.md`，确认无重复主路径后再加路由。
- **金额与安全**：金额相关 API 禁止 float（见 §5.5）；配置类 API 须鉴权，敏感字段脱敏（见 §9）。
- **记账与审计结构对称**：同类操作（列表、详情、状态变更）在记账主线与审计主线上命名模式应一致，降低学习成本。

---

## 十、安全与边界规则

- **API Key、数据库密码等敏感信息只放在后端环境变量**，不暴露到前端。
- **财务数据操作必须有审计日志**：包括期间关闭、reopen、损益结转等关键操作。
- **已结账期间的数据修改需要特殊权限或不可逆流程**，符合会计实务。

---

## 十一、测试与验收

- **每个功能完成后，AI 给出测试地址和验证方法**。
- **用户测试后反馈问题，AI 优先修复**。
- **财务逻辑错误 = 最高优先级 bug**，与技术缺陷分开处理。
- **财务主流程和财务逻辑修复应尽量达到 L6**（测试与真实数据验证完成）。

---

## 十二、本地化大模型与客户数据合规（中介机构视角）

完整部署方案见 `deploy/FDE_LOCAL_LLM_COMPLIANCE.md`，本节只列开发时必须遵守的约束。

- **大模型是可选增强，不是前提**：未配置 AI 时，导入、规则风险、借贷平衡、试算、结账控制必须照常可用；新功能不得把大模型变成主流程的硬依赖，须保留 `ai_fallback_to_rules` 兜底路径。
- **统一走模型路由**：调用大模型必须通过 `resolve_effective_llm_config`（`manual` / `local` / `cloud` / `auto`），不得在业务代码里硬编码模型地址、云端 API 或 Key。
- **默认数据不出域**：客户序时账、凭证、合同、底稿、身份信息等原始资料，默认只发往本地模型（Ollama / vLLM）；新增调用云端模型的路径，必须由配置显式开启，并在 PR 中说明会发出哪些字段。
- **解析与推理分开**：文档/票据解析用 `ai_local_model`，合规审查与 Agent 推理用 `ai_reasoning_model`，避免同一模型在本地显存中互相挤占。
- **向量库本地化**：Qdrant 使用本地路径（`qdrant_local_path`），不得引入外部托管向量服务作为默认选项。
- **AI 输出标注**：界面与导出报告中，AI 生成内容须可识别为「建议 / 草稿」，不能与人工确认的审计结论、律师意见混在同一字段。

---

## Cursor Cloud specific instructions

云端 Agent 运行在 Ubuntu 虚拟机上，与本地 Windows / Trae 环境不同：

- **后端环境**：按 §4.2 的 Linux 步骤创建 `backend/.venv`；若 `ensurepip` 报错，先安装 `python3.12-venv`。之后每个新 shell 先 `source backend/.venv/bin/activate`，再执行 `pnpm dev:backend` 或 pytest。
- **长期运行的服务**（后端、前端 dev server）放在 tmux 会话中启动，启动后用 `curl http://127.0.0.1:8000/health` 确认返回 `{"status":"ok"}`。
- **数据库**：默认使用 `backend/finance_audit.db`（SQLite），无需 PostgreSQL、Redis 或 Docker 即可开发和测试；VM 上通常没有 Docker，`deploy/` 下的 compose 脚本无法在云端验证，只做语法与文档层面检查。
- **大模型**：VM 上没有 Ollama，也不应配置真实云端 Key；涉及 LLM 的逻辑用 pytest 的 `monkeypatch` 模拟（参考 `backend/tests/test_compliance_llm_vector.py`），并确认规则兜底路径可用。
- **最低验证**：后端改动跑相关 `backend/tests/test_*.py`；前端改动跑 `pnpm lint:frontend` 与 `pnpm build:frontend`。
- **不要提交**本地产生的 `backend/.venv/`、`*.log`、`finance_audit.db` 变更、`qdrant_local_storage/` 等运行时文件；`pip install -e` 会改动已被跟踪的 `backend/finance_vector_audit_backend.egg-info/`，提交前用 `git checkout -- backend/finance_vector_audit_backend.egg-info` 还原。
