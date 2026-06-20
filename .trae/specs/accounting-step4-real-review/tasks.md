# Tasks：会计模式 Step4 真实分录复核

## Task 1：编写子 spec 三件套
- [x] 新建 `.trae/specs/accounting-step4-real-review/spec.md`
- [x] 新建 `.trae/specs/accounting-step4-real-review/tasks.md`（即本文件）
- [x] 新建 `.trae/specs/accounting-step4-real-review/checklist.md`

## Task 2：实施改造
- [x] 删除 `Step4ReviewEntries.tsx` 中的 `mockEntries` 与本地 `Entry` 接口
- [x] 引入 `useSearchParams`、`api`、`AccountingEntry`
- [x] `useEffect` 中根据 `jobId` 调用 `api.listEntries(jobId)` 加载真实分录
- [x] 表格列改为 `voucher_no / entry_line_no / voucher_date / account_name / summary / debit_amount / credit_amount / counterparty`，`counterparty` 兼容 null
- [x] verified 状态改用 `Map<number, boolean>` 维护（本地）
- [x] 上一步按钮：`navigate('/accounting/step/3?jobId=...&periodId=...')`
- [x] 下一步按钮：`navigate('/accounting/step/5?jobId=...')`
- [x] 缺失 jobId 时显示 Alert 警告并禁用下一步

## Task 3：验证
- [x] 前端 `npm run lint`（即 `tsc --noEmit`）通过
- [x] 手工核对：spec 中 5 条 ADDED Requirements 全部落地

## Task Dependencies

- Task 1 → Task 2 → Task 3 串行
