# Debug Session: period-review-loss

Status: [OPEN]
Session ID: period-review-loss

## Symptom
用户反馈 `jobId=20`：
1. 同一个文件对应多个分录、多个会计期间时，没有分别识别对应期间，反而尽数落到当前选择期间。
2. 从 Step3 进入 Step4 复核调整后，大面积记录被删除，仅保留约 200 条记录。

## Business Boundary
- Domain: D04 凭证生命周期 + D05 序时簿导入解析。
- In Scope: jobId=20 的跨期间凭证日期保留、Step3 到 Step4 草稿保存完整性、分页后保存行为。
- Out of Scope: 报表、结账、审计任务、支持性文件和导航逻辑。

## Hypotheses
1. Step3 草稿生成对已导入序时簿仍按 selected period 夹紧日期，导致跨期间分录全部显示/提交到 periodId=1。
2. Step4 只保存了前端当前分页或前 200 条数据，导致从 Step3 到 Step4 后记录数量大幅减少。
3. 后端 commit 接口在保存草稿时仍按当前 period 强校验或改写日期，导致跨期间信息丢失。
4. jobId=20 后端原始 `accounting_entries` 已完整且跨期间正确，但 Step3/Step4 接口返回或提交阶段截断。
5. 前端分页组件改变后，保存按钮拿到的是分页后的数据而不是全部 `drafts` 状态。

## Evidence
- 初始 jobId=20：`entry_count=72058`，实际 `accounting_entries=82352`，明显存在重复/错误提交数据。
- 初始月份分布：`2021-06` 有 61764 条，远高于其他月份；这批记录 `source_file_id is null`，说明是 Step3 保存草稿时二次新建出来的错误分录，不是源文件解析分录。
- 源文件解析分录：`source_file_id=3`，共 20588 条，日期范围 `2022-05-31` 到 `2026-03-31`，跨 47 个月。
- Step4 记录只剩约 200 条的根因：`GET /api/entries` 中 `return query.limit(200).all()` 硬限制。
- `commit_drafts` 会 `_clamp_date(voucher_date, period)`，导致跨期间草稿按当前 periodId 被夹紧。

## Fix Summary
- Step3 保存已导入序时簿草稿时，不再调用 `commit_drafts` 重建分录；改为复用已有 `source_entry_id` 对应分录。
- `job.entry_count` 改为按数据库中当前任务真实分录数量回写，不再累加导致虚增。
- `GET /api/entries` 改为分页响应：`items / total / limit / offset`，移除 200 条固定截断。
- Step4 前端改为服务端分页读取，显示真实总数，并支持 50/100/200/500 条每页。
- 清理 jobId=20 的错误重复分录：删除 `source_file_id is null` 的 61764 条错误记录，保留源文件解析出的跨期间分录。

## Current Verification Status
- jobId=20 当前：20588 条分录，191 张凭证，日期范围 `2022-05-31` 到 `2026-03-31`。
- 月份分布：47 个月，第一批从 `2022-05` 开始，最后到 `2026-03`。
- `/api/entries?import_job_id=20&limit=100&offset=0` 返回分页结构，不再固定截断 200 条。
- 后端 `/health` 正常；前端 `http://127.0.0.1:5173/` 正常。
- Awaiting user verification before cleanup.
