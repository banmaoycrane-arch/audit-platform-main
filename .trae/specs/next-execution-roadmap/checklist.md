# Checklist（路线图验证）

> ⚠️ **历史验证记录**（约 2026-06）。**不得**作为当前完成依据。  
> **代码真值**: [code-truth-status.md](../../documents/code-truth-status.md) — 666 测试用例、368 API、L6 待验收。

## 队列 1：period-close-pl-transfer
- [x] `period_close_service.py` 含 `auto_pl_transfer` + `reverse_pl_transfer`
- [x] API `POST /api/accounting-periods/{id}/pl-transfer` 与 `/reverse` 已挂载
- [x] 前端 `AccountingPeriodsPage` 含「损益结转 / 反结转」按钮
- [x] pytest `test_period_close_pl_transfer.py` 3/3 通过
- [x] 前端 `tsc --noEmit` 通过

## 队列 2：accounting-step4-real-review
- [x] 子 spec `.trae/specs/accounting-step4-real-review/spec.md` 存在
- [x] 子 spec `tasks.md`、`checklist.md` 存在
- [x] Step4 不再使用 `mockEntries`，改读真实草稿
- [x] commit 后跳转 Step5 时携带 jobId
- [x] pytest + 前端 lint 通过

## 队列 3：audit-report-export
- [x] 子 spec 三件套存在
- [x] 后端 `routes_audit_export.py` 提供 docx/xlsx 下载
- [x] 审计 Step6 真实下载，移除 setTimeout mock
- [x] pytest + 前端 lint 通过

## 队列 4：business-cycle-audit Task 5/6
- [x] `GET /api/business-cycles` 200
- [x] `POST /api/business-cycles/detect-breaks` 返回断裂结果
- [x] `GET /api/business-cycles/{id}/risks` 返回循环后风险
- [x] 单测覆盖率 ≥ 80%（service 层）
- [x] pytest 全部通过

## 队列 5：internal-control-audit Task 5/6
- [x] `GET /api/internal-controls` 200
- [x] `POST /api/internal-controls/test` 返回测试结果
- [x] `GET /api/internal-controls/alerts` 200
- [x] 单测覆盖率 ≥ 80%（service 层）
- [x] pytest 全部通过

## 队列 6：dashboard-home-and-day-book-import
- [x] 子 spec 三件套存在
- [x] 首页 Dashboard 显示 4 类 KPI（凭证数 / 未结转期间 / 未复核风险 / 最近发现）
- [x] 审计 Step3 提供「导入序时簿」入口
- [x] `source_type=audit_day_book` 流向正确，序时簿字段不丢失
- [x] pytest + 前端 lint 通过

## 总体出口
- [x] 5 个待执行队列在本路线图 `tasks.md` 全部勾选
- [x] 每个队列的子 spec 自身 `checklist.md` 全部勾选
- [ ] ~~后端 `pytest backend/tests` 全量通过（88 passed）~~ → **须按 666 用例重新验证**（见 code-truth-status.md）
- [ ] 前端 `npm run lint` 通过（仍建议 CI 复验）
