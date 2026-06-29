# Debug Session: step5-review-export

Status: [OPEN]
Session ID: step5-review-export

## Symptom
用户在 `http://127.0.0.1:5173/ledger/vouchers/step/5?jobId=20&periodId=1` 导出失败：
`存在未复核通过的分录（需 verified 或 ready）`，并返回大量 `entry_ids`。

## Business Boundary
- Domain: D04 凭证复核、确认入账与导出。
- In Scope: jobId=20 的 review_status 分布、Step4 放行条件、批量复核动作、Step5 导出错误可读性。
- Out of Scope: 序时簿解析规则、报表生成规则、结账逻辑、审计任务。

## Hypotheses
1. Step4 只用当前分页 `entries` 判断 `allVerified`，当前页全勾选后就允许进入 Step5，但其他分页仍为 draft。
2. Step4 批量复核只更新当前页选中记录，没有提供“复核全部分录”的安全操作。
3. Step5 后端导出校验是正确的，但返回全部未复核 entry_ids，导致错误信息过长、页面体验差。
4. jobId=20 在清理重复数据后保留下来的源文件分录 review_status 仍大多是 draft。
5. 前端“已复核 x/y”统计只统计当前页，误导用户认为全量已复核。

## Evidence
- jobId=20 当前 `review_status` 分布：`draft=20088`, `verified=500`, `total=20588`。
- Step5 后端拒绝导出是正确的，因为仍有 20088 条未复核通过。
- Step4 旧逻辑：`verifiedCount = entries.filter(...)`、`allVerified = entries.length > 0 && verifiedCount === entries.length`，只统计当前分页。
- Step4 批量复核旧逻辑仅提交 `selectedRowKeys`，只能覆盖当前选择页。
- Step5 旧错误：后端返回完整未复核 ID 列表，导致错误消息巨大。

## Fix Summary
- 新增 `/api/entries/review-stats`，返回全任务复核统计：`total / verified / ready / unreviewed / status_counts`。
- Step4 改为按全任务统计控制是否允许进入 Step5，不再按当前页判断。
- Step4 增加“全量标记全部 N 条”操作，明确提示会影响所有分页。
- 新增 `/api/entries/jobs/{job_id}/review-all`，支持按任务全量更新复核状态。
- Step5 后端错误改为结构化摘要：未复核数量 + 前 20 个样例 ID，不再返回完整 2 万个 ID。
- 前端错误解析兼容全局异常包装后的 `error.details`，展示可读错误。

## Verification
- `/api/entries/review-stats?import_job_id=20` 返回：`total=20588`, `verified=500`, `unreviewed=20088`。
- `/api/import-jobs/20/post` 仍正确返回 400，但错误体只包含 `unreviewed_count=20088` 和 20 个样例 ID。
- 后端 py_compile 通过。
- VS Code 诊断：`routes_entries.py`、`routes_export.py`、`Step4ReviewEntries.tsx`、`client.ts` 均无错误。
- 前端服务可访问：`http://127.0.0.1:5173/`。

## Current State
- 未自动把 20088 条 draft 改成 verified，因为这是会计复核控制点，应由用户在 Step4 点击“全量标记全部 20588 条”确认。
- Awaiting user verification before cleanup.
