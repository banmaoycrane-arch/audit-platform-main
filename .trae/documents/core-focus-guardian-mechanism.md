# 核心主线守护机制（Core Focus Guardian）

## 1. 目的

确保项目当前阶段（核心记账闭环 + 导入解析引擎）不被非核心任务稀释。所有开发、测试、文档工作必须围绕这两大主线展开，避免陷入小功能、优化项、扩展需求的陷阱。

## 2. 当前核心主线

| 主线 | 目标 | 关键完成标志 |
|---|---|---|
| **核心记账闭环** | 实现从建账 → 科目 → 期初 → 凭证 → 损益结转 → 三表生成的完整闭环 | 标准会计案例跑通，报表恒等式成立 |
| **导入解析引擎** | 实现文件导入 → 双引擎解析 → 知识库增强 → 生成台账/凭证的闭环 | 真实业务文件解析准确，可生成可用凭证草稿 |

## 3. 任务优先级评估标准

所有任务在创建或执行前必须按以下标准分类：

| 标签 | 英文 | 定义 | 优先级 |
|---|---|---|---|
| 核心闭环 | `CORE-CLOSURE` | 直接属于核心记账闭环或导入解析引擎的功能/修复/测试 | P0 |
| 核心支持 | `CORE-SUPPORT` | 为核心模块提供必要支持但不直接属于核心功能（如权限、迁移、基础字段扩展） | P1 |
| 基础设施 | `INFRA` | 环境、配置、CI/CD、构建等 | P2（仅阻塞时） |
| 锦上添花 | `NICE-TO-HAVE` | 优化、美化、非核心扩展 | 禁止 |
| 偏离 | `DRIFT` | 与当前核心主线无关或会显著分散资源 | 必须拒绝或延期 |

## 4. 每日目标设定流程

### 4.1 时间

每个工作日开始时（或前一日结束时）更新 `.trae/daily-focus.md`。

### 4.2 内容模板

```markdown
# 每日焦点（YYYY-MM-DD）

## 今日核心目标（最多 3 项）

1. [ ] [CORE-CLOSURE] 目标描述
2. [ ] [CORE-SUPPORT] 目标描述
3. [ ] [CORE-CLOSURE] 目标描述

## 今日禁止项

- 不处理 NICE-TO-HAVE 优化
- 不扩展非核心模块
- 不深入讨论架构长期愿景

## 完成检查

- [ ] 至少 1 项 P0 任务完成
- [ ] 没有新增 P2/P3 任务投入
- [ ] 代码修改集中在核心模块路径
```

### 4.3 对齐规则

- 每日目标不得超过 3 项。
- 必须至少包含 1 项 `CORE-CLOSURE` 任务。
- 禁止在单日目标中安排 `NICE-TO-HAVE` 任务。

## 5. 每周目标设定流程

### 5.1 时间

每周一早晨更新 `.trae/weekly-focus.md`。

### 5.2 内容模板

```markdown
# 每周焦点（YYYY-MM-DD 至 YYYY-MM-DD）

## 本周核心目标（最多 5 项）

1. [ ] [CORE-CLOSURE] 核心闭环目标 1
2. [ ] [CORE-CLOSURE] 核心闭环目标 2
3. [ ] [CORE-CLOSURE] 导入解析引擎目标
4. [ ] [CORE-SUPPORT] 必要支持任务
5. [ ] [CORE-CLOSURE] 测试/验证目标

## 本周里程碑

- 日期 D：完成 XX
- 日期 D+2：完成 YY
- 日期 D+4：完成 ZZ

## 风险与偏离预警

| 风险 | 状态 | 应对措施 |
|---|---|---|
| 用户提出非核心需求 | 待观察 | 记录到 backlog，本周不处理 |
| 核心模块依赖阻塞 | 待观察 | 当日转为 P1 支持，24h 内解决 |
```

## 6. 每日工作进展回顾与方向校准

### 6.1 回顾问题清单

每个工作日结束时，对照以下问题：

1. 今天完成了哪些 `CORE-CLOSURE` 任务？
2. 今天是否投入了 `NICE-TO-HAVE` 或 `DRIFT` 任务？
3. 今天的代码修改是否集中在核心模块路径？
4. 是否有核心阻塞需要明日优先处理？
5. 是否更新了 `.trae/daily-focus.md` 的完成状态？

### 6.2 校准动作

| 情况 | 动作 |
|---|---|
| 连续 2 天无 P0 完成 | 暂停所有非核心任务，强制聚焦核心模块 |
| 单日出现 >30% 时间投入非核心 | 次日缩减非核心任务，回归核心 |
| 核心模块依赖阻塞 | 将依赖任务提升为 P1，限定 24h 解决 |
| 用户提出新需求 | 判断是否属于核心主线，否则记录 backlog |

## 7. 自动偏离检测规则

### 7.1 检测脚本

运行 `scripts/focus_drift_detector.py` 检查当前工作区是否偏离核心主线。

### 7.2 触发条件

满足以下任一条件即触发偏离提醒：

1. **文件路径偏离**：修改文件不在核心模块路径内（见 8.1）。
2. **新增非核心模块**：检测到新增独立页面、独立 API 路由、独立服务。
3. **连续无核心进展**：每日/每周回顾中连续 2 天无 `CORE-CLOSURE` 完成。
4. **用户请求偏离**：用户连续 3 个请求均与核心模块无关。
5. **Git 提交主题偏离**：最近 3 次提交均不包含 `CORE-CLOSURE` 或核心模块关键词。

### 7.3 提醒输出

检测脚本输出格式：

```text
⚠️ 核心主线偏离提醒
- 偏离类型：文件路径偏离
- 涉及文件：frontend/src/pages/SomeNewPage.tsx
- 建议：该文件不属于核心记账闭环或导入解析引擎，请确认是否必须今日处理
```

## 8. 核心模块路径白名单

### 8.1 后端核心模块路径

```
backend/app/services/accounting/           # 会计服务
backend/app/services/entries/              # 分录/凭证服务
backend/app/services/reports/              # 报表服务
backend/app/services/period_close/          # 损益结转/期间
backend/app/services/opening_balances/    # 期初余额
backend/app/services/chart_of_accounts/   # 会计科目
backend/app/services/parser_engine/       # 解析引擎
backend/app/services/import_engine/       # 导入引擎
backend/app/api/routes_entries.py         # 凭证 API
backend/app/api/routes_reports.py          # 报表 API
backend/app/api/routes_accounting_periods.py  # 期间 API
backend/app/api/routes_opening_balances.py    # 期初 API
backend/app/api/routes_import_jobs.py      # 导入 API
backend/app/api/routes_parser_engine.py    # 解析引擎 API
backend/app/models/ledger.py
backend/app/models/accounting_entry.py
backend/app/models/accounting_period.py
backend/app/models/opening_balance.py
backend/app/models/chart_of_accounts.py
backend/app/db/models.py 中的 Entity / Organization / Ledger / AccountingEntry 相关部分
backend/alembic/versions/                   # 仅核心模块迁移
backend/tests/acceptance/accounting/       # 核心记账测试
backend/tests/acceptance/parser_engine/    # 解析引擎测试
backend/samples/                           # 标准业务样例
```

### 8.2 前端核心模块路径

```
frontend/src/pages/LedgerPage.tsx
frontend/src/pages/EntryListPage.tsx
frontend/src/pages/EntryGenerationPage.tsx
frontend/src/pages/ChartOfAccountsPage.tsx
frontend/src/pages/OpeningBalancePage.tsx
frontend/src/pages/AccountingPeriodPage.tsx
frontend/src/pages/ReportsPage.tsx
frontend/src/pages/ParserEngineManagementPage.tsx
frontend/src/pages/ParserEngineConfigPage.tsx
frontend/src/pages/ImportJobPage.tsx
frontend/src/services/accounting.ts
frontend/src/services/entries.ts
frontend/src/services/reports.ts
frontend/src/services/parserEngine.ts
frontend/src/stores/ledgerStore.ts
```

## 9. Trae 自定义指令

在 `.trae/custom-instructions.md` 中写入以下内容，让 AI 在每次对话开始时自动对齐核心主线：

```markdown
# 核心主线提醒

当前项目阶段：核心记账闭环 + 导入解析引擎。

在每次执行任务前，请：
1. 优先读取 `.trae/daily-focus.md` 和 `.trae/weekly-focus.md`。
2. 判断用户请求是否属于 CORE-CLOSURE。
3. 如果是 NICE-TO-HAVE 或 DRIFT，必须提醒用户并建议延期。
4. 执行完成后更新 daily-focus.md 的完成状态。
```

## 10. 执行流程图

```
每日开始
  ├─ 读取 weekly-focus.md
  ├─ 制定 daily-focus.md（最多 3 项，至少 1 项 P0）
  └─ 开始工作
        ├─ 每个任务前打标签（CORE-CLOSURE / CORE-SUPPORT / INFRA / NICE-TO-HAVE / DRIFT）
        ├─ 工作过程中运行 focus_drift_detector.py
        ├─ 偏离时输出提醒并校准
        └─ 每日结束更新 daily-focus.md 并做回顾

每周开始
  ├─ 回顾上周 daily-focus.md
  ├─ 制定 weekly-focus.md（最多 5 项）
  └─ 校准下周方向
```

## 11. 结论

核心主线守护机制通过**目标文件 + 优先级标签 + 自动检测脚本 + Trae 自定义指令**四层手段，确保项目在当前阶段不偏离核心记账闭环和导入解析引擎两大主线。所有团队成员和 AI 助手都应遵循本机制。
