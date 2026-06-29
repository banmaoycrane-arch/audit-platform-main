# 下一阶段执行路线图（队列 1–6 统筹）Spec

## Why

工作区已有 20+ 份 spec，但「下一步该做什么、按什么顺序做、哪些 spec 已完成、哪些缺失」需要一份单一可信来源（single source of truth）来对齐。用户给出 6 个队列：

1. **队列 1**：period-close-pl-transfer（期末损益结转）
2. **队列 2**：记账 Step4 流程修正
3. **队列 3**：audit-report-export（审计报告导出）
4. **队列 4**：business-cycle-audit Task5/Task6
5. **队列 5**：internal-control-audit Task5/Task6
6. **队列 6**：dashboard-home → audit-day-book-import

本 spec 不重复实现细节，仅作为「调度文档」：盘点每个队列的 spec 现状、识别缺失、安排执行顺序与依赖、约束最小可交付集合，避免重复造 spec、避免一次性铺太大。

## What Changes

- 盘点 6 个队列对应的现存 spec 状态：
  - 队列 1：[period-close-pl-transfer]（**已完成**，pytest 3/3 通过）— 不再做新工作。
  - 队列 2：**spec 缺失** → 本路线图新增 change-id `accounting-step4-real-review` 占位（不在本 spec 内写细节，留给后续 spec 文档实现）。
  - 队列 3：**spec 缺失**（已有 `export-accounting-package` 是「记账模式 Step5 账簿导出」，与「审计模式审计报告导出」不同）→ 新增 change-id `audit-report-export` 占位。
  - 队列 4：[business-cycle-audit] 已有 spec，Task 1–4 完成，剩余 **Task 5（API）+ Task 6（测试）**。
  - 队列 5：[internal-control-audit] 已有 spec，Task 1–4 完成，剩余 **Task 5（API）+ Task 6（测试）**。
  - 队列 6：**spec 缺失** → 新增 change-id `dashboard-home-and-day-book-import` 占位（包含两个子主题：首页 dashboard 与审计模式 Step3 序时簿导入入口）。
- 给出 5 个待执行队列的执行顺序与依赖关系。
- 不在本 spec 内编写代码、不替代被引用 spec 的内容。

## Impact

- 受影响 specs（仅引用，不修改）：
  - `business-cycle-audit/tasks.md`、`internal-control-audit/tasks.md`、`export-accounting-package/spec.md`
- 受影响代码：
  - 本 spec 阶段不直接修改代码。每个队列在其自己的 spec 文档里实施时再修改。

## ADDED Requirements

### Requirement: 路线图单一可信来源

系统的 `.trae/specs/next-execution-roadmap/` 目录 SHALL 提供 5 个待执行队列的状态、依赖、执行顺序，作为团队对齐的唯一文档。任何队列状态变更（完成、调整、新增）SHALL 同步到本路线图 `tasks.md` 与 `checklist.md`。

#### Scenario: 队列状态查询
- **WHEN** 阅读 `next-execution-roadmap/tasks.md`
- **THEN** 能直接看到每个队列对应的 spec 文件路径、当前完成度、下一步动作

### Requirement: 缺失 spec 的占位规划

对于队列 2、3、6 这 3 个尚无 spec 的工作项，路线图 SHALL 在 `tasks.md` 中给出占位任务（占位仅记录 change-id 与一句话目标），具体 spec 文档由后续单独的 spec 流程产出，不在本 roadmap 内展开实现细节。

#### Scenario: 占位任务可识别
- **WHEN** 进入待执行的占位队列
- **THEN** 该队列任务 SHALL 第一步是「编写本队列的 spec.md / tasks.md / checklist.md」，第二步起才是实施

### Requirement: 队列执行顺序约束

执行顺序按用户给出的队列编号优先级：队列 2 → 队列 3 → 队列 4 → 队列 5 → 队列 6。本路线图 SHALL 明确每个队列的入口前置（依赖）与出口完成标志（验证条件）。

#### Scenario: 出口完成标志
- **WHEN** 一个队列的所有 task 完成
- **THEN** `checklist.md` 中该队列的 checkbox 全部勾选；后端 pytest 通过；前端 `tsc --noEmit` 通过

## MODIFIED Requirements

无。本路线图不修改任何已有 spec 的需求；仅引用它们的现状。

## REMOVED Requirements

无。

## 队列依赖图（概览）

```
队列1 ✅ period-close-pl-transfer (DONE)
   │
   ▼
队列2  accounting-step4-real-review     ← 需要先建 spec
   │
   ▼
队列3  audit-report-export              ← 需要先建 spec
   │
   ▼
队列4  business-cycle-audit T5/T6       ← spec 已有
   │
   ▼
队列5  internal-control-audit T5/T6     ← spec 已有
   │
   ▼
队列6  dashboard-home-and-day-book-import  ← 需要先建 spec
```

注：队列 4 与队列 5 后端 API 之间无强依赖，理论上可并行，但为控制 PR 体量与风险，建议串行落地。

## 注意事项（面向初学者 + 财务视角）

1. **路线图 ≠ 实施文档**：本 spec 不是把 5 个队列的细节都写一份。每个缺失 spec 的队列，第一步是产出它自己的 `spec.md`，第二步才进实施。这避免了一次性铺太大、改不动的反模式。
2. **队列 4/5 的 Task 5（API）属于「财务/审计可见的对外接口」**：`GET /api/business-cycles`、`POST /api/internal-controls/test` 这些接口是会计师看得见的「业务封装」，类似 ERP 系统对外开放的功能菜单；编程上注意 RESTful 风格、状态码语义、错误信息可读。
3. **队列 6 中「序时簿（day book）」=「序时账簿、连续登记的所有凭证流水」**，是审计师拿到的最重要的原始数据形态。导入入口的设计要保留凭证号、日期、借贷方向等所有关键列，不能像之前 Step4 mock 那样丢失字段。
