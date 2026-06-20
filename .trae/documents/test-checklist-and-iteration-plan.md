# 项目测试清单与推进顺序计划

## Summary

本计划基于工作区历史记忆、需求域索引（D01-D13）、核心业务概念边界、任务治理文档，梳理项目的最终目标、各需求域现状与优先级，并输出一份按依赖顺序排列的测试清单，供推进项目迭代时使用。

---

## 一、项目最终目标

### 1.1 财务业务视角

构建一个 **财务向量审计系统**，支持：

```
原始资料 / 序时簿 / 会计分录
  → 结构化导入与解析
  → 标签、向量、AI 草稿或风险线索
  → 凭证复核 / 审计测试
  → 审计发现 / 风险复核 / 报告导出
```

核心是记账闭环和审计闭环的对称结构：

- **记账主线**：基础资料 → 凭证录入/导入 → 复核 → 落库 → 结账 → 报表
- **审计主线**：审计计划 → 证据/序时簿导入 → 审计测试 → 审计发现 → 报告导出

AI/向量作为辅助工具，不能绕过人工复核和确定性会计规则。

### 1.2 技术架构视角

前后端分离系统：

| 层级 | 技术选型 |
|---|---|
| 前端 | React + TypeScript + Vite + Ant Design |
| 后端 | FastAPI + SQLAlchemy |
| 数据库 | SQLite（本地默认）/ PostgreSQL（可选） |
| 向量 | Qdrant（可选） |
| 测试 | pytest（后端）+ 自动化脚本 |

---

## 二、需求域（D01-D13）概览与当前状态

> 状态判断依据：`requirements-domain-index.md` + 搜索代理探索结果 + 历史测试通过记录

| 域 | 名称 | 主规格 | 状态 | 说明 |
|---|---|---|---|---|
| D01 | 身份认证与访问控制 | user-auth-system | 稳定/有 bugfix | 登录注册主线有回归风险 |
| D02 | 团队、账套、项目、上下文 | team-multi-ledger-management | 稳定 | Team/Ledger/Project 边界已冻结 |
| D03 | Shell、导航、工作台、模块入口 | saas-shell-and-navigation | 基本稳定 | SaaS Shell 已就位，部分模块是占位 |
| D04 | 凭证生命周期 | unify-voucher-input-modes | 重点推进 | Step1-5 已落地，AI 路径和导出需真实数据验证 |
| D05 | 原始资料导入与解析 | adaptive-import-engine | 稳定 | 导入引擎有基础能力 |
| D06 | 审计证据与审计流程 | audit-day-book-import | 重点推进 | Step1-6 已落地，真实闭环需验证 |
| D07 | 基础资料 | basic-data-pages / enhance-chart-of-accounts-design | 基本稳定 | 科目、往来、期初有页面 |
| D08 | 会计期间、结账、快照、报表 | accounting-period-snapshot / financial-statements | 重点推进 | 期间和报表已有，需真实数据对账 |
| D09 | EntryTag、语义、向量、AI 草稿 | entry-tag-vector-sync / govern-ai-voucher-evidence-tags | 发展中 | EntryTag 有 API，向量和 AI 草稿需验证 |
| D10 | Agent 与执行型助手 | agent-lightweight-llm-api | 发展中 | Agent Chat 已有入口 |
| D11 | 业务模块 | — | 预留 | 银行、税务、固定资产、进销存暂无主规格 |
| D12 | 缺陷修复与环境诊断 | — | 持续进行 | JWT、注册、登录等已有多次 bugfix |
| D13 | 项目计划、复盘、路线图 | — | 文档治理 | 大量 planning/historical 文档，不作为实现依据 |

---

## 三、测试清单与推进顺序

### 推荐测试顺序原则

```
阻塞验证优先  →  基础底座验证  →  主流程闭环验证  →  扩展功能验证
```

---

### 第 0 步：环境与基础设施验证（优先验证）

**目标**：确认前后端能正常启动，数据库可用。

| 序号 | 测试项 | 验证方法 | 对应端口/路径 |
|---|---|---|---|
| T0-1 | 后端健康检查 | `GET http://127.0.0.1:8000/health` | 后端 8000 |
| T0-2 | 前端启动 | `pnpm dev:frontend`，浏览器访问 http://127.0.0.1:5173 | 前端 5173 |
| T0-3 | Vite Proxy 正常 | 访问 `/api/health` 应转发到后端 | — |
| T0-4 | 数据库文件存在 | 检查 `backend/finance_audit.db` | — |
| T0-5 | pytest 通过 | `pnpm test:backend`，已有记录 143 passed | — |

**说明**：此步验证当前环境可用，为后续测试提供基准。

---

### 第 1 步：身份认证与上下文（D01 + D02）

**目标**：登录 → 创建/加入团队 → 选择账套，确认数据边界清晰。

| 序号 | 测试项 | 验证方法 | 对应路由/页面 |
|---|---|---|---|
| T1-1 | 用户注册 | 前端注册页面或 API `POST /api/auth/register` | — |
| T1-2 | 用户登录 | 前端登录页面或 API `POST /api/auth/login`，获取 Token | 登录页 |
| T1-3 | Token 鉴权 | 调用需鉴权的 API（如 `/api/entries`），带 Token | — |
| T1-4 | 创建/加入团队 | API `POST /api/team` 或团队管理页面 | 团队管理 |
| T1-5 | 创建账套 | API `POST /api/ledger` 或账套管理页面 | 账套管理 |
| T1-6 | 账套切换上下文 | 切换默认账套，确认后续操作以 `ledger_id` 为边界 | — |

**关键验证点**：

- Token 过期处理是否正常
- 未登录时受保护页面是否正确跳转
- 账套切换后数据是否隔离

---

### 第 2 步：基础资料底座（D07）

**目标**：科目、往来单位、期初余额能正常维护，是记账闭环的前置条件。

| 序号 | 测试项 | 验证方法 | 对应页面/API |
|---|---|---|---|
| T2-1 | 会计科目增删改查 | 科目管理页面或 API `/api/coa` | 基础资料 → 会计科目 |
| T2-2 | 往来单位增删改查 | 往来单位页面或 API `/api/counterparties` | 基础资料 → 往来单位 |
| T2-3 | 期初余额录入 | 期初余额页面或 API `/api/opening-balances`，检查借贷平衡 | 基础资料 → 期初余额 |
| T2-4 | 空白建账 vs 模板导入 | 科目空白建账流程、行业模板导入预览确认 | — |

**关键验证点**：

- 借贷不平衡时是否报错
- 科目编码唯一性检查
- 往来单位与 Counterparty 口径一致

---

### 第 3 步：会计期间与结账底座（D08）

**目标**：期间能正常创建、结账、损益结转，是凭证和报表的前置条件。

| 序号 | 测试项 | 验证方法 | 对应页面/API |
|---|---|---|---|
| T3-1 | 创建会计期间 | 期间管理页面或 API `/api/accounting-periods`，验证 `ledger_id` 归属 | 会计期间 |
| T3-2 | 期间连续性 | 相邻期间起止日期不重叠 | — |
| T3-3 | 已结账期间不可修改 | 结账后尝试修改凭证，检查是否阻止 | — |
| T3-4 | 损益结转 | 执行结转，检查本年利润科目是否有数 | 结账操作 |
| T3-5 | 反结账 | 撤销结账，检查数据回滚 | — |
| T3-6 | 资产负债表平衡 | 资产 = 负债 + 所有者权益 | 报表页面 |
| T3-7 | 利润表数据正确 | 收入 - 费用 = 本期净利润，与结转数一致 | 报表页面 |

**关键验证点**：

- 结账状态机：`open → pl_transferred → closed` 转换是否正常
- 损益结转借贷是否平衡
- 报表取数是否正确消费期间和期初数据

---

### 第 4 步：记账凭证主流程闭环（D04）

**目标**：Step1 → Step5 全链路可走通，凭证可落库、导出。

| 序号 | 测试项 | 验证方法 | 对应页面/路由 |
|---|---|---|---|
| T4-1 | Step1 — 账套与期间选择 | 选账套、选期间，检查上下文传递 | /accounting/step/1 |
| T4-2 | Step2 — 原始资料导入（文件） | 上传 CSV/Excel，检查解析结果和质量报告 | /accounting/step/2 |
| T4-3 | Step2 — 原始资料导入（AI 路径） | AI 生成凭证草稿，检查创建会计期间是否成功 | /accounting/step/2?inputMode=ai_generated |
| T4-4 | Step3 — 分录生成与展示 | 检查生成的借方/贷方分录是否平衡 | /accounting/step/3 |
| T4-5 | Step4 — 凭证复核 | 复核草稿，检查通过/修改/驳回流程 | /accounting/step/4 |
| T4-6 | Step5 — 凭证落库与导出 | 确认落库，检查凭证号连续性，导出 Excel/JSON | /accounting/step/5 |
| T4-7 | 手工录入凭证 | 直接在凭证页面手工录入，检查借贷平衡 | 凭证管理 |
| T4-8 | 凭证号跳号检测 | 导入序时簿时检查凭证号连续性 | Step2 导入 |
| T4-9 | EntryTag 绑定 | 给分录打标签，检查标签与分录关联 | Step3/Step4 |
| T4-10 | 草稿 vs 正式凭证区分 | 草稿不进入报表，删除草稿不影响正式数据 | — |

**关键验证点**：

- AI 路径 Step2 创建期间是否成功（已知历史 bug，需重点验证）
- 借贷不平衡凭证是否阻止落库
- 凭证号连续性

---

### 第 5 步：审计流程主流程闭环（D06）

**目标**：Step1 → Step6 全链路可走通，审计发现可记录、报告可导出。

| 序号 | 测试项 | 验证方法 | 对应页面/路由 |
|---|---|---|---|
| T5-1 | Step1 — 审计计划/任务创建 | 创建审计项目，关联账套 | /audit/step/1 |
| T5-2 | Step2 — 审计证据上传 | 上传合同、发票、序时簿等文件 | /audit/step/2 |
| T5-3 | Step3 — 序时簿导入与分录 | `source_type=audit_day_book` 导入，检查凭证号分组和借贷平衡 | /audit/step/3 |
| T5-4 | Step4 — 审计测试执行 | 执行内控测试、业务循环测试，检查发现数量 | /audit/step/4 |
| T5-5 | Step5 — 审计发现记录 | 新增/编辑/复核审计发现，检查持久化 | /audit/step/5 |
| T5-6 | Step6 — 审计报告导出 | 导出 Word/Excel 报告，检查报告数据完整性 | /audit/step/6 |
| T5-7 | 业务循环审计 | 执行采购、销售、资金等业务循环测试 | 内控/业务循环 |
| T5-8 | 内控测试 | 内控问卷或穿行测试，记录结论 | 内控测试页面 |

**关键验证点**：

- 序时簿导入借贷不平衡是否拦截
- 审计发现是否持久化到数据库
- 报告数据是否与审计测试结论一致

---

### 第 6 步：报表验证（D08）

**目标**：报表数据与凭证、期初、结账数据一致。

| 序号 | 测试项 | 验证方法 | 对应页面/报表 |
|---|---|---|---|
| T6-1 | 资产负债表 | 录入期初 + 本期凭证后，检查资产负债表是否平衡 | 报表 → 资产负债表 |
| T6-2 | 利润表 | 执行损益结转后，检查利润表净利润 = 本年利润科目余额 | 报表 → 利润表 |
| T6-3 | 报表与凭证数据一致性 | 报表中科目余额与分录明细汇总一致 | — |
| T6-4 | 跨期间报表 | 切换不同会计期间，报表数据是否正确切换 | — |
| T6-5 | 报表快照 | 结账后生成快照，后续修改凭证不影响已结账报表 | — |

**关键验证点**：

- 报表不平衡时，应回到凭证和损益结转解决，不硬调平

---

### 第 7 步：AI / 向量 / Agent 增强验证（D09 + D10）

**目标**：AI 辅助工具能生成建议和草稿，但不能绕过人工复核。

| 序号 | 测试项 | 验证方法 | 对应功能 |
|---|---|---|---|
| T7-1 | AI 凭证草稿生成 | 上传原始资料，AI 推荐科目和分录，检查草稿质量 | Step2 AI 路径 |
| T7-2 | EntryTag 语义标签 | 给分录打 EntryTag，检查向量同步是否成功 | 分录标签 |
| T7-3 | DocumentTag 文档分类 | 上传合同/发票，检查 DocumentTag 分类是否合理 | 原始资料 |
| T7-4 | 向量检索 | 用关键词检索历史分录，检查检索结果相关性 | 分录查询 |
| T7-5 | AI 证据充分性判断 | 证据不足时 AI 是否给出风险提示，而非直接确认 | AI 辅助 |
| T7-6 | Agent Chat 对话 | 与 Agent 对话，检查回答是否准确，是否绕过权限 | Agent 页面 |
| T7-7 | 风险线索提示 | AI 分析序时簿，检查是否输出风险线索 | 审计证据 |

**关键验证点**：

- AI 草稿必须有"人工复核"环节，不能直接正式入账
- 向量同步不应阻塞主流程

---

### 第 8 步：边界与回归验证

**目标**：确保修改未破坏既有功能和边界规则。

| 序号 | 测试项 | 验证方法 |
|---|---|---|
| T8-1 | Team/Ledger/Project 边界隔离 | Team 下新增账套，不影响其他 Team 数据 |
| T8-2 | ledger_id 强制过滤 | 所有正式财务数据按 `ledger_id` 过滤 |
| T8-3 | 已结账期间保护 | 结账后修改凭证，应报错或需特殊权限 |
| T8-4 | Token 刷新 | Token 过期后系统是否正确引导重新登录 |
| T8-5 | 导航连续性 | Step1-5 之间的前进后退，上下文是否保持 |
| T8-6 | 回归测试套件 | `pnpm test:backend` 全部通过（143 个用例） |

---

## 四、按依赖关系的测试排序

```
T0（环境）
  └─ T1（认证+上下文）
       ├─ T2（基础资料）→ T3（期间+结账）
       │                        └─ T4（记账凭证）→ T6（报表）
       └─ T5（审计流程）
              └─ T7（AI/Agent）
                   └─ T8（边界回归）
```

---

## 五、角色分工建议

| 角色 | 负责测试域 |
|---|---|
| 用户（会计师） | T4 记账凭证、T5 审计流程、T6 报表的**业务逻辑验收** |
| AI 助手 | T1-T8 所有**技术实现验证**，包括 API、数据库、回归 |
| 用户 + AI 共同 | T3 期间结账、T7 AI 证据充分性（会计逻辑 + 技术实现共同判断） |

---

## 六、验证命令速查

```powershell
# 环境验证
curl http://127.0.0.1:8000/health

# 后端测试
pnpm test:backend

# 前端构建
pnpm build:frontend

# 前端类型检查
pnpm lint:frontend

# 启动后端
pnpm dev:backend

# 启动前端
pnpm dev:frontend
```

---

---

## 八、T0 执行结果（2026-06-20）

| 验证项 | 结果 | 详情 |
|---|---|---|
| pytest 全量回归 | ✅ PASS | 152 passed, 1418 warnings, EXIT_CODE=0 |
| 前端 TypeScript 编译 | ✅ PASS | `pnpm tsc --noEmit` 退出码 0 |
| 后端服务端口 | ⚠️ 未启动 | 8000 端口当前无服务（需 `pnpm dev:backend` 启动） |
| SQLite 数据库 | ✅ 可用 | pytest 成功访问 `backend/finance_audit.db` |
| 主要 warnings | ⚠️ 可改善 | `datetime.utcnow()` 弃用警告（建议迁移到 `datetime.now(datetime.UTC)`） |

pytest 详细结果已保存至 `pytest_result.txt`。

---

## 九、项目当前完整状态快照

### 9.1 后端 API 路由（已注册）

已确认在 `backend/app/main.py` 中挂载的路由：

| 路由模块 | 功能 |
|---|---|
| routes_auth | 认证：登录、注册、Token |
| routes_team | 团队管理 |
| routes_ledger | 账套管理 |
| routes_accounting_periods | 会计期间、结账、反结账 |
| routes_accounting_units | 内部核算单位 |
| routes_coa | 会计科目 |
| routes_counterparties | 往来单位 |
| routes_opening_balances | 期初余额 |
| routes_entries | 分录查询 |
| routes_entry_generation | AI 分录生成 |
| routes_entry_tags | EntryTag 标签管理 |
| routes_imports | 原始资料导入任务 |
| routes_files | 文件管理 |
| routes_risks | 风险识别 |
| routes_transactions | 事务一致性 |
| routes_reports | 财务报表（资产负债表、利润表） |
| routes_audit_tests | 审计测试 |
| routes_audit_export | 审计报告导出 |
| routes_business_cycles | 业务循环审计 |
| routes_internal_controls | 内控测试 |
| routes_document_parsing | 文档解析 |
| routes_agent | Agent Chat |
| routes_dashboard | 工作台仪表盘 |
| routes_project | 项目管理 |
| routes_lifecycle | 账套生命周期 |
| routes_entities | 会计主体 |
| routes_materials | 物料 |
| routes_binding_requests | 绑定申请 |

### 9.2 前端路由（已注册）

已确认在 `frontend/src/App.tsx` 中挂载的路由：

**记账主流程**：
- `/accounting/step/1` — 选类型（含 /ledger/vouchers/step/1 双路径）
- `/accounting/step/2` — 原始资料导入
- `/accounting/step/3` — 生成草稿分录
- `/accounting/step/4` — 复核调整
- `/accounting/step/5` — 确认入账与导出

**审计主流程**：
- `/audit/step/1` — 选审计范围
- `/audit/step/2` — 审计证据上传
- `/audit/step/3` — 序时簿导入
- `/audit/step/4` — 执行审计测试
- `/audit/step/5` — 复核审计发现
- `/audit/step/6` — 导出审计报告

**基础资料**：
- `/basic/coa` — 会计科目
- `/basic/counterparties` — 往来单位
- `/basic/opening-balances` — 期初余额
- `/basic/org-units` — 组织架构
- `/basic/personnel` — 人员

**报表**：
- `/reports/trial-balance` — 试算平衡表
- `/reports/balance-sheet` — 资产负债表
- `/reports/income-statement` — 利润表

**其他**：
- `/entries`、`/ledger/entries` — 分录查询
- `/agent` — Agent 对话
- `/periods`、`/accounting-periods` — 会计期间管理
- `/workspace` — 工作台首页

### 9.3 占位模块（待实现）

以下模块已注册路由但页面为占位符：

| 路由 | 说明 |
|---|---|
| `/basic/materials` | SKU/物料 |
| `/basic/warehouses` | 仓库 |
| `/bank/accounts` | 银行账户 |
| `/bank/third-party-accounts` | 三方支付账户 |
| `/bank/aggregate-accounts` | 聚合账户 |
| `/bank/journal` | 日记账 |
| `/bank/settings` | 账户设置 |
| `/bank/reconciliation` | 自动对账 |
| `/tax/invoices` | 发票管理 |
| `/tax/assistant` | 涉税助手 |
| `/fixed-assets/cards` | 资产卡片 |
| `/fixed-assets/depreciation` | 折旧计提 |
| `/inventory/purchase-in` | 采购入库 |
| `/inventory/stock-flow` | 库存流水 |
| `/ledger/books` | 账簿管理 |
| `/ledger/general-ledger` | 总账 |
| `/ledger/subsidiary-ledger` | 明细账 |

### 9.4 已知技术债务

| 类型 | 说明 |
|---|---|
| `datetime.utcnow()` 弃用 | 1418 个 warnings 全部来源于此，建议统一迁移到 `datetime.now(datetime.UTC)` |
| httpx 迁移 | FastAPI testclient 使用了 `starlette.testclient`（已弃用），建议升级到 httpx2 |
| Qdrant 兼容性 | 客户端版本检查失败（可设置 `check_compatibility=False` 跳过） |
| organization_id 兼容 | 部分 API 仍暴露 `organization_id`，新需求应使用 `ledger_id` |

---

## 十、建议迭代推进路径

### 立即可做（阻塞级别）

1. **启动后端服务**：`pnpm dev:backend`，确认 8000 端口正常响应
2. **验证 T1**：登录注册流程，确认 Token 鉴权正常
3. **验证 T3**：创建会计期间，确认 `ledger_id` 归属正确
4. **验证 T4 Step2 AI 路径**：历史上出现过"创建会计期间失败"bug，重点验证

### 下一迭代（主流程闭环）

1. **T2 基础资料**：科目 + 往来 + 期初余额录入
2. **T4 记账全链路**：Step1-5 用真实数据走通
3. **T6 报表**：资产负债表平衡验证
4. **T5 审计全链路**：Step1-6 用真实序时簿数据走通

### 后续迭代（增强与扩展）

1. **T7 AI/向量**：EntryTag 向量同步、证据充分性
2. **T8 回归**：修复后重新运行 pytest
3. **占位模块**：按 D11 优先级逐步实现银行、税务、固定资产、进销存
