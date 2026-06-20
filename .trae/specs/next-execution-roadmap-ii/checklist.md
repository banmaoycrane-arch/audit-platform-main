# Checklist

## 队列 D：transactional-design API
- [x] `GET /api/transactions` 200
- [x] `GET /api/transactions/{id}` 200，未知 ID 404
- [x] `POST /api/transactions/{id}/rollback` pending 事务可回滚
- [x] 已 committed 事务回滚返回 400
- [x] `GET /api/transactions/summary` 返回各状态计数
- [x] pytest test_transactions_api.py 全部通过（10/10）

## 队列 A：基础资料前端页
- [x] [ChartOfAccountsPage.tsx](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/BasicData/ChartOfAccountsPage.tsx) 已实现 CRUD
- [x] [CounterpartiesPage.tsx](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/BasicData/CounterpartiesPage.tsx) 已实现 CRUD
- [x] MainShell 侧边栏含「基础资料」三级菜单
- [x] auto-generate-entries-from-source/tasks.md Task 7 全部 [x]

## 队列 C：document-parsing API
- [x] [routes_document_parsing.py](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/app/api/routes_document_parsing.py) 暴露 4 类解析端点
- [x] [test_document_parsing_api.py](file:///e:/projects/finance-vector-audit/wroksapce20260616/backend/tests/test_document_parsing_api.py) 5 用例通过
- [x] document-parsing-engine/tasks.md Task 6/7 [x]

## 总体出口
- [x] 后端 pytest 全量通过（98 passed）
- [x] 前端 lint 通过
