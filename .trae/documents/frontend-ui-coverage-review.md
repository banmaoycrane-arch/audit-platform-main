# 前端 UI 覆盖度复盘 Plan

> 截图分析对象：达普记账（截图来自用户）的 SAAS 风格记账界面。
> 比对目标：本工作区 `$(cwd)/.trae/specs/` 已立的需求规划与现有前端实现，识别在 UI 维度上**已有 / 缺口 / 部分覆盖** 的模块，并给出后续 spec 拆分建议。

---

## Phase 1 - 探索结果摘要

### 截图中识别到的 UI 模块（按区域）

#### 顶部 Tab（工作区切换）
1. 首页（仪表盘）
2. 凭证管理 / 凭证列表 / 凭证字汇总
3. 期初凭证科目设置 / 期初科目余额
4. 账户 / 业务类别 / 关键字摘要
5. 记账凭证 / 结算抵销 / 账户与凭证
6. 入库列表 / 出库列表 / 库存列表 / 库存记账
7. 资产卡片 / 折旧记录 / 折旧明细凭证生成 / 折旧明细记录
8. 资产负债表（推断同行还有：利润表、科目余额表）

#### 左侧导航
- 顶部账簿：`123`
- 业务类别 / 业务管理 / 企业账号 / 三明账户（推测为银行账户/资金账户）/ 关键词
- 资产管理子树：资产计算 / 资产记账 / 折旧明细记录 / 折旧明细凭证 / 资产凭证

#### 主内容区
- 期初数据概况（年度切换 2025）
- 凭证处理：`新增凭证`、`凭证列表` 两个常用入口
- 凭证 / 余额 / 资金账户 / 科目余额表 / 资产负债表 / 利润表 等 KPI 卡片
- 财务概况曲线图：收入 / 库存 / 费用 / 税金 / 利润

#### 顶栏右侧
- 搜索单据数据
- 编辑账簿
- 帮助
- 客服悬浮入口

### 现有项目规划与实现对照

> ✅ 已规划且已编码 / 🔵 已规划，前端薄弱 / 🟡 部分规划 / ❌ 未规划

| UI 模块（截图） | spec 归属 | 状态 |
|----------------|----------|------|
| 凭证管理 / 列表 | `auto-generate-entries-from-source` + `entry-line-number` | ✅ 后端齐备；前端仅 Step3 草稿表 |
| 凭证字汇总 | `summary-library` + `auto-generate-entries-from-source` | 🔵 服务有，前端无独立页 |
| 期初凭证科目设置 | `auto-generate-entries-from-source` (CoA 部分) | 🟡 后端 CoA CRUD 完成；前端无 |
| 期初科目余额 | — | ❌ **完全未规划** |
| 账户（资金账户） | `entity-semantic-mapping`（边缘相关）+ `auto-generate-entries-from-source`（账户从 CoA 表映射） | 🟡 间接覆盖，无独立"资金账户档案"概念 |
| 业务类别 | `summary-library`（凭证字 + 业务关键词） | 🟡 服务侧有，前端无 |
| 关键字摘要 | `summary-library` | 🔵 后端有模板库，前端无 |
| 客户 / 供应商 | `auto-generate-entries-from-source`（Counterparty 档案） | 🟡 后端 CRUD 完成；前端无 |
| 入库 / 出库 / 库存 / 库存记账 | `document-parsing-engine`（入库/出库单解析） | 🟡 仅解析，**无库存账核算**与库龄、结存计算 |
| 资产卡片 / 折旧 | — | ❌ **完全未规划** |
| 资产凭证 / 折旧凭证 | — | ❌ **完全未规划** |
| 结算 / 抵销 | — | ❌ **完全未规划**（应付应收对账） |
| 资产负债表 / 利润表 / 科目余额表 | — | ❌ **完全未规划** |
| 首页仪表盘 / KPI / 财务曲线 | `summarize-requirements`（仅 MVP 概览） | ❌ 前端无仪表盘 |
| 全局搜索（单据/数据） | — | ❌ **未规划** |
| 账簿切换 / 编辑账簿 | `entity-semantic-mapping`（主体范围） | 🟡 后端模型已存在；前端未实现 |
| 顶部 Tab 多工作区 | — | ❌ **未规划**（信息架构层面） |
| 帮助 / 客服 | — | ❌ 未规划 |

### 现有前端真实页面（实测）

```text
src/pages/
  HomePage / 模式选择卡片
  AccountingMode/Step1..Step5
  AuditMode/Step1..Step6
  EntriesPage  (分录列表)
  RisksPage
  Error 页（仅 UI）
```

> 信息架构是"两个引导式向导"，**没有 SAAS 标配的左侧主导航 + 顶部账簿切换 + 多 Tab 工作区**，与截图差距大。

### 路由技术栈（用户问）

```text
框架：React 18 + TypeScript + Vite
路由：react-router-dom v6+（在 main.tsx / App.tsx 中以 createBrowserRouter / RouterProvider 或 <Routes> 形式声明）
组件库：Ant Design
状态：组件本地 useState；尚无统一 Zustand / Redux / TanStack Query
样式：内联 style + Antd 默认主题；无 CSS Module / Tailwind
```

---

## Phase 2 - 需要澄清的取舍（已用结构化建议代替提问）

不阻塞主线推进，将建议直接放入 Phase 3。如需调整可在下一轮指令中告诉我。

---

## Phase 3 - 提案：UI 覆盖度补齐计划

### 提案 0：信息架构升级（前置，必做）

新建 spec：**`saas-shell-and-navigation`**

- 引入 SAAS 标准布局：
  - 顶栏（账簿切换 / 全局搜索 / 帮助 / 用户）
  - 左侧主导航（折叠式）
  - 多 Tab 工作区（凭证管理/资产管理/库存管理/报表/基础资料）
  - 路由仍用 `react-router-dom`，但分两层：Shell 路由（带导航布局）+ 子模块嵌套路由
- 引入 `@tanstack/react-query` 做服务端状态、`zustand` 做轻量本地状态（可选）
- 旧的"记账模式 / 审计模式向导"改为 Shell 内的两个工作流入口，不再是顶级路由

### 提案 1：补齐缺失的 spec（建议优先级）

| 优先级 | 新 spec | 价值 | 依赖 |
|------|---------|------|------|
| P0 | `saas-shell-and-navigation` | UI 重构地基 | 无 |
| P0 | `basic-data-pages` | CoA / Counterparty / 业务类别 / 关键词等已有后端的前端 CRUD | 提案 0 |
| P0 | `opening-balances` | 期初科目余额录入 + 试算平衡 | CoA、AccountingPeriod |
| P0 | `financial-statements` | 资产负债表 / 利润表 / 科目余额表生成 | AccountingPeriod、AccountingEntry、CoA |
| P1 | `funds-account-management` | 资金账户档案（银行/现金/支付平台），区别于 CoA 1002 | CoA、Counterparty |
| P1 | `inventory-ledger` | 库存账（入库 / 出库 / 库存 / 库龄 / 结存价 FIFO/加权平均） | 现有入库单/出库单解析 |
| P1 | `fixed-assets` | 资产卡片 + 折旧规则 + 折旧凭证生成 | CoA、AccountingPeriod |
| P1 | `dashboard-home` | 首页仪表盘（KPI、收入/费用/利润曲线） | 报表服务 |
| P2 | `settlement-offset` | 应收应付对账 / 抵销 | Counterparty、AccountingEntry |
| P2 | `global-search-and-help` | 全局搜索单据、帮助系统 | Shell、各模块索引 |

### 提案 2：当前已落地能力的"上架"

下面这些后端能力已经做完，但**前端没有页面承接**，应当在 `basic-data-pages` 与 `dashboard-home` 中补齐：

- 会计科目 CRUD（`/api/coa`）
- 对方单位 CRUD（`/api/counterparties`）
- 会计期间结账/反结账（`/api/accounting-periods`）
- 审计发现持久化（`/api/audit-tests`）
- 业务循环 / 内控 / 文档解析 / 实体（已挂 API）

### 提案 3：路由结构示意

```text
/                        → 首页（仪表盘）
/books/:bookId            → 账簿 Shell
  /home                   → 首页 KPI
  /vouchers               → 凭证管理（列表 + 新增 + 凭证字汇总）
  /opening                → 期初科目设置 / 余额
  /basic                  → 基础资料
    /coa                  → 会计科目
    /counterparties       → 对方单位
    /funds-accounts       → 资金账户
    /business-types       → 业务类别
    /keywords             → 关键词摘要库
  /inventory              → 库存管理
    /inbound /outbound /stock /ledger
  /assets                 → 资产管理
    /cards /depreciation /vouchers
  /reports                → 报表
    /balance-sheet /profit /trial-balance
  /settlement             → 结算/抵销
  /audit                  → 审计模式（保留原有 6 步）
  /accounting             → 记账模式（保留原有 5 步）
```

### 提案 4：本期不动，但需明确

- **报表生成依赖期初科目余额 + 期间分录**：在做 `financial-statements` 之前必须先做 `opening-balances`，否则报表数据缺起点。
- **库存与资产凭证生成会反哺到自动生成分录引擎**：库存出库结转成本、固定资产折旧凭证都属于 `转字`，是 `entry_generation_service` 的扩展点。

---

## Phase 4 - 下一步行动建议

按依赖顺序建议实施：

1. **新建 spec**：`saas-shell-and-navigation` → 改造前端整体布局；
2. **新建 spec**：`basic-data-pages` → 把已有后端 CoA / Counterparty 等暴露到 UI；
3. **新建 spec**：`opening-balances` → 期初余额；
4. **新建 spec**：`financial-statements` → 三大报表；
5. 之后再排期 `inventory-ledger` / `fixed-assets` / `dashboard-home` / `settlement-offset` / `global-search-and-help`。

---

## 编程常识 + 财务视角补充

**编程常识（路由）**：

- React 项目里"页面切换 = 路由"，常用 `react-router-dom`：
  - 顶级 `BrowserRouter` 提供路由上下文
  - `<Routes>` 列出所有 URL 与组件的对应关系
  - SAAS 后台一般会做"嵌套路由"：外层是统一的 Shell（顶栏 + 侧栏），内层根据 URL 切换中间区域；不需要每个页面都重写顶栏
- 多 Tab 工作区两种实现：
  1. **真路由 Tab**：每个 Tab 是一个 URL，刷新可恢复，Outlook/钉钉风格
  2. **本地状态 Tab**：Tab 仅存在前端内存，刷新丢失，IDE 风格
  - 财务/审计软件建议选 1，方便审计留痕（用户访问哪个页面可在 access log 看到）

**财务视角对应**：

- 截图里这套界面其实就是按"账"的抽象组织：
  - 总账 → 凭证管理、凭证字汇总、科目余额表
  - 明细账 → 凭证列表、入库/出库/库存
  - 资产账 → 资产卡片、折旧
  - 期初 → 期初科目余额（年初余额，是所有报表的起点）
- 您的项目目前主要做了"导入 → 自动生成 → 审计"三段，但少了**期初**这一头与**报表**这一尾，所以从财务师视角看，账还没"闭合"。补上这两块，软件才有完整的"账实一致 → 出账"能力。

---

## 结论一句话

> 截图反映的 SAAS 标准模块（信息架构、期初余额、报表、资产、库存、仪表盘、全局搜索、结算抵销）**目前在项目规划中只覆盖了约 35%**，其中前端只承接了不到 15%。建议立刻新增 `saas-shell-and-navigation`、`basic-data-pages`、`opening-balances`、`financial-statements` 四个 spec，按顺序补齐。
