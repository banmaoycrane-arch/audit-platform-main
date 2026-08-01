# E2 导入聚类 — 任务清单

> 对应 [spec.md](./spec.md) §7 E2 阶段
> 状态：✅ 完成（2026-08-01）
> 范围：在已入账分录（`AccountingEntry`）上做规则聚类 → 候选事件 → 人工确认生成工单

## 设计决策（D1–D8）

| 编号 | 决策 | 说明 |
|------|------|------|
| D1 | 聚类维度：往来 + 月份 | `counterparty_id` 优先；为 NULL 时兜底用 `original_entity_name`；`voucher_date` 截到月份 |
| D2 | 最小阈值：≥2 分录 | 单条分录不生成候选事件，避免事件膨胀 |
| D3 | 前端入口 | `EconomicEventsPage` 顶部「从导入生成事件」按钮 → 弹窗选 `import_job_id`（或全账簿 + 日期范围）→ 候选列表（可编辑标题/类型/勾选）→ 一键创建 |
| D4 | 不内置 LLM 命名 | 首版规则模板「{往来} {yyyy-mm} 业务」+ `event_type='manual'`；LLM 后置到 E3 |
| D5 | 不需要新 Alembic 迁移 | `EconomicEvent` 模型已支持 `source='import'` + `source_id` + `event_type='import_cluster'` |
| D6 | 新增 2 个 API | `POST /api/economic-events/cluster-suggest`（返回候选，不创建）+ `POST /api/economic-events/cluster-confirm`（批量创建+挂分录+推进到 collecting） |
| D7 | 新增服务层 | `backend/app/services/shared/economic_event_cluster_service.py`（`suggest_clusters` + `confirm_clusters`） |
| D8 | 新增测试 | `backend/tests/test_economic_event_cluster_api.py` 覆盖 6 场景 |

## 后端任务

- [x] T1 新增 `economic_event_cluster_service.py`
  - [x] `suggest_clusters(db, ledger_id, import_job_id=None, date_from=None, date_to=None, min_entries=2)` → 返回候选列表（含 cluster_key、title、event_type、occurred_on、entry_ids、display_amount、counterparty_name）
  - [x] `confirm_clusters(db, ledger_id, clusters, actor_user_id, import_job_id)` → 批量创建事件 + 挂分录 + 推进到 `collecting`，返回事件列表
  - [x] 跳过已挂在 `import_cluster` 事件上的分录（避免重复聚类，幂等）
- [x] T2 `routes_economic_events.py` 新增 2 端点
  - [x] `POST /cluster-suggest` 请求体：`import_job_id?`、`date_from?`、`date_to?`、`min_entries?=2`；响应：候选列表
  - [x] `POST /cluster-confirm` 请求体：`import_job_id?`、`clusters: [{title, event_type?, occurred_on?, entry_ids: [int]}]`；响应：创建的事件列表

## 前端任务

- [x] T3 `api/client.ts` 增加 2 个方法 + 1 个类型
  - [x] `suggestEconomicEventClusters(ledgerId, payload)` → `EconomicEventClusterSuggestion[]`
  - [x] `confirmEconomicEventClusters(ledgerId, payload)` → `EconomicEvent[]`
  - [x] `EconomicEventClusterSuggestion` 类型导出
- [x] T4 新增 `ClusterSuggestModal.tsx`
  - [x] 表单：导入任务下拉（来自 `listImportJobs`） + 日期范围 + 最小阈值
  - [x] 候选列表：可勾选、可编辑标题、显示分录数与金额
  - [x] 一键创建 → 调 `confirmEconomicEventClusters` → 关闭并刷新列表
- [x] T5 `EconomicEventsPage.tsx` 顶部增加「从导入生成事件」按钮触发弹窗

## 测试任务

- [x] T6 `test_economic_event_cluster_api.py` 覆盖
  - [x] 空聚类（无分录）返回空列表
  - [x] 正常聚类（同往来 + 同月 ≥2 分录）返回 1 个候选
  - [x] 阈值过滤（<2 分录的组不出现；跨月分录不合并）
  - [x] confirm 幂等：已挂在 import_cluster 事件上的分录不会被二次聚类
  - [x] confirm 后事件状态推进到 `collecting`，关联分录正确
  - [x] 按 `import_job_id` 过滤

## 验证任务

- [x] T7 `pytest` 全绿（894 → 900，新增 6 个测试）
- [x] T8 `tsc --noEmit` 0 错误
- [x] T9 `vitest run` 77/77 通过
- [x] T10 文档真值同步：`code-truth-status.md` §3.4 经济事件工单行 + `checklist.md` E2 段勾选
