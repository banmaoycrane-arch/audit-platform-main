# Tasks

## 队列 D：transactional-design Task 4-6（事务 API + 测试）
- [x] Task D.1：新增 `backend/app/api/routes_transactions.py`
  - `GET /api/transactions?context_type=&context_id=&status=`
  - `GET /api/transactions/{id}` 详情（含 transaction + operations 摘要）
  - `GET /api/transactions/{id}/operations` 操作列表
  - `POST /api/transactions/{id}/rollback` 手动回滚（仅 pending 可回滚，已 committed 返回 400）
  - `GET /api/transactions/summary?status=` 统计计数
- [x] Task D.2：在 `backend/app/main.py` 注册路由
- [x] Task D.3：新增 `backend/tests/test_transactions_api.py`，至少 5 用例：
  - test_list_transactions_empty
  - test_get_transaction_404
  - test_create_via_manager_then_list_returns_one
  - test_get_transaction_detail_with_operations
  - test_manual_rollback_pending_transaction
  - test_rollback_already_committed_returns_400
  - test_summary_returns_status_counts
- [x] Task D.4：勾选 transactional-design/tasks.md Task 4/5/6
- [x] Task D.5：验证 pytest 通过

## 队列 A：auto-generate-entries-from-source Task 7（已完成，仅勾选）
- [x] Task A.1：在 [auto-generate-entries-from-source/tasks.md](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/specs/auto-generate-entries-from-source/tasks.md) 中：
  - SubTask 7.1 / 7.2 / 7.3 改 `[x]`
  - Task 7 的 `[/]` 改为 `[x]`
- [x] Task A.2：[auto-generate-entries-from-source/checklist.md](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/specs/auto-generate-entries-from-source/checklist.md) 同步

## 队列 C：document-parsing-engine Task 6-7（已完成，仅勾选）
- [x] Task C.1：在 [document-parsing-engine/tasks.md](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/specs/document-parsing-engine/tasks.md) 中 Task 6 / Task 7 改 `[x]`
- [x] Task C.2：[document-parsing-engine/checklist.md](file:///e:/projects/finance-vector-audit/wroksapce20260616/.trae/specs/document-parsing-engine/checklist.md) 同步

## 出口验证
- [x] 后端全量 pytest 通过（98 passed）
- [x] 前端 `npm run lint` 通过

# Task Dependencies
- Task D.4/D.5 依赖 D.1-D.3 完成
- A、C 与 D 互不依赖，可并行
