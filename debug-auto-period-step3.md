# Debug Session: auto-period-step3

Status: [OPEN]
Session ID: auto-period-step3

## Symptom
用户访问 `http://127.0.0.1:5173/ledger/vouchers/step/3?jobId=21` 时提示：
“缺少导入任务或会计期间，请从导入资料步骤重新进入并选择会计期间，否则无法生成草稿。”

用户期望：系统应根据已识别分录日期，自适应匹配各分录对应的会计期间，而不是强制只有一个 periodId。

## Business Boundary
- Domain: D04 凭证草稿生成 + 会计期间识别。
- In Scope: Step3 缺少 periodId 时的前端拦截、后端 period_id 必填、jobId=21 分录日期与会计期间覆盖关系、草稿 metadata 中分录级期间识别。
- Out of Scope: 报表、结账、审计任务、税务规则、总账过账引擎。

## Hypotheses
1. Step3 前端因 `!periodId` 直接拦截，导致后端无法根据分录日期自动识别期间。
2. 后端 generate-entries 请求体把 `period_id` 设为必填，接口层无法处理缺省期间。
3. jobId=21 的原始分录已带正确 voucher_date，可通过 voucher_date 匹配 AccountingPeriod。
4. 数据库 AccountingPeriod 缺少覆盖 jobId=21 日期范围的期间，自动识别会失败或只识别部分。
5. 后续 Step4/Step5 仍依赖单一 periodId，URL 缺失时需要兼容保留 jobId 流程。

## Evidence Plan
- 查询 jobId=21 的任务、分录数量、日期月份分布。
- 查询 AccountingPeriod 覆盖范围。
- 读取 Step3 前端 periodId 拦截逻辑和 generate-entries 请求 schema。
- 先采集证据，不修改业务逻辑。

## Timeline
- Initialized debug session.
