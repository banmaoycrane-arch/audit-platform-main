# Debug Session: daybook-step3-performance

Status: [OPEN]
Session ID: daybook-step3-performance

## Symptom
用户反馈 `http://127.0.0.1:5173/ledger/vouchers/step/3?inputMode=ai_generated&jobId=19&periodId=1`：
1. 页面性能损失很大，占用内存很多。
2. 似乎只识别到了 18 号凭证，还有很多没有识别出来。

## Business Boundary
- Domain: D04 凭证生命周期 + D05 序时簿导入解析。
- In Scope: jobId=19 的序时簿识别完整性、后端返回数据规模、Step3 页面渲染/内存压力。
- Out of Scope: 报表、审计任务、支持性文件归档、其他无关导航和权限逻辑。

## Hypotheses
1. 后端一次性返回 1 万+ 分录草稿，前端表格全量渲染导致浏览器内存和性能大幅下降。
2. 解析器实际只落库到 18 号凭证附近，后续行因表头识别、空行、日期、凭证号向下填充或异常行被截断。
3. 后端已完整识别，但前端 Step3 只展示部分数据，用户看到的是渲染/分页/排序问题。
4. jobId=19 的 source file、source_type、status 或 storage_path 与 jobId=18 不一致，导致走了不同解析链路。
5. 凭证号是文本格式，排序/去重/分组逻辑错误，使页面看起来只识别到 18 号。

## Evidence
- jobId=19 初始检查：`status=completed`, `entry_count=10595`，但 `accounting_entries` 实际为 `21190` 条，刚好是 10595 的两倍。
- 初始凭证范围：`count(distinct voucher_no)=191`, `min=记-0001`, `max=记-0191`，说明不是只识别到 18 号凭证。
- 初始 Step3 接口返回：HTTP 200，响应体约 `41719981` 字节（约 41.7MB），说明页面高内存与全量重载/全量渲染相关。
- 清理重复数据后：`accounting_entries` 为 `10595` 条，凭证范围仍为 `记-0001` 到 `记-0191`。
- 前端修复后：表格启用分页，默认 100 条/页，固定滚动区域。
- 后端草稿瘦身后：Step3 接口返回约 `4867640` 字节（约 4.9MB），凭证日期保留源序时簿日期 `2022-05-31`，不再被 periodId=1 夹紧为 2021-06-30。

## Confirmed Root Cause
1. 重复导入：同一 job 被重复触发后没有先判断已有分录，导致 10595 行重复成 21190 行。
2. 前端性能：Step3 表格 `pagination=false`，一次性渲染全部分录。
3. 返回体过重：已导入序时簿生成草稿时附带了大量 metadata/tags，并且重写凭证号和摘要，不适合大批量序时簿。
4. 显示误导：序时簿日期被会计期间夹紧，导致显示日期偏离源文件。

## Fix Summary
- `process_day_book_import` 增加已有分录检查，避免同一 job 重复落库。
- 清理 jobId=19 重复分录，从 21190 条恢复为 10595 条。
- Step3 前端表格启用分页与固定滚动区域。
- 已导入序时簿草稿保留原凭证号、原摘要、原行号和源凭证日期。
- 草稿返回只带最小 metadata，tags 为空，降低返回体和前端内存压力。

## Current Verification Status
- 后端 `/health` 正常。
- 前端 `http://127.0.0.1:5173/` 正常。
- jobId=19：10595 条分录，191 张凭证，范围 `记-0001` 至 `记-0191`。
- Step3 接口返回约 4.9MB，较修复前 41.7MB 明显下降。
- Awaiting user verification before debug cleanup.
