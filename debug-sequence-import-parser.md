# Debug Session: sequence-import-parser

Status: [OPEN]
Session ID: sequence-import-parser

## Symptom
用户在 `http://127.0.0.1:5173/ledger/vouchers/step/3?inputMode=ai_generated&jobId=18&periodId=1` 上传其他财务软件标准格式序时簿后，未解析出任何会计分录，LLM 也未产生有效识别结果。

## Hypotheses
1. 文件已经上传并创建 `ImportJob=18`，但后端解析流程没有把该文件识别为序时簿/日记账类型，导致使用了错误解析路径。
2. 表头识别规则过窄，只匹配当前项目内置格式，无法识别其他财务软件常见列名，例如凭证字号、科目编码、借方、贷方、摘要、日期等变体。
3. 解析结果可能已经生成在临时字段或 draft 中，但 Step 3 页面读取的字段/接口不一致，导致前端显示“0 笔”。
4. LLM 兜底没有触发，可能是解析引擎在规则失败后直接返回空结果，未进入 LLM fallback。
5. LLM 已触发但输入内容为空、被截断、模型配置缺失或调用失败未暴露，导致用户看到没有任何识别。

## Evidence Plan
- 只添加运行时采集日志，先不修改业务逻辑。
- 采集 jobId、文件元数据、识别出的表头、解析分支、规则解析行数、LLM fallback 是否触发、LLM 输入/输出摘要、最终 entry_count。

## Timeline
- Initialized debug session.
- Static DB observation for `jobId=18`: job exists, `source_type=ai_generated`, `status=created`, `entry_count=0`; one source file exists but `text_extract_status=pending`, `extracted_text` empty, `job.draft_data=None`. This suggests parsing was never triggered before Step 3.
- Added instrumentation only in `routes_entry_generation.py` around `generate_entries` to capture job state, source file parse state, generated draft count, and blocked status.
- Pre-fix runtime evidence: Step3 generated 1 blocked placeholder draft; source file remained `text_extract_status=pending`, `extracted_text` empty, `entry_count=0`.
- Parser isolated evidence: using the actual Excel absolute path, `parse_entries` detected template `标准中文`, matched `凭证日期/凭证号/摘要/科目/借方金额/贷方金额`, parsed `10595` rows, `0` error rows, quality score `100.0`.
- Root cause evidence: `SourceFile.storage_path` was stored as `storage\uploads\...xlsx`; when called from project root it resolved to project-root storage, but actual file was under `backend\storage\uploads`. Dedicated service therefore parsed `0` rows in the formal chain.
- Fix evidence: after resolving storage paths against `BACKEND_DIR`, direct `process_day_book_import` changed `jobId=18` from `0` to `10595` accounting entries.
- Step3 chain evidence: after calling `generate_entries(18, period_id=1)`, database shows `import_jobs.status='completed'`, `entry_count=10595`, and `accounting_entries` has `10595` rows for `import_job_id=18`.
- Draft evidence: `generate_drafts` returns `10595` drafts and `blocked_count=0`; first draft account is `100202 银行存款_农商行`.

## Confirmed Root Cause
- The LLM did not appear to work because Step3 never handed valid file content into the parser/LLM path for this uploaded sequence journal.
- There was also a real rule issue: header alias mapping previously allowed `科目` to be treated as `summary`; fixed so `科目` maps to account name and account code/name can be split from values such as `100202 银行存款_农商行`.
- Large sequence-journal import also needed batch insertion; per-row flush/tag/vector writes made the formal path too fragile for 10k+ rows.

## Fix Summary
- Uploaded file paths are now resolved relative to the backend directory, not the process current directory.
- `ai_generated` jobs that look like sequence journals are auto-routed through day-book import on Step3.
- Standard Chinese headers and account code/name splitting are supported.
- Sequence journal persistence uses batch insert for stable import of large day books.
- Existing imported sequence-journal entries are treated as sufficient accounting evidence when generating Step3 drafts, so they are not blocked as missing invoice/bank/contract evidence.

## Current Verification Status
- Backend `/health` returned `200 {"status":"ok"}` after restart.
- `jobId=18` currently has `10595` persisted accounting entries and import job status `completed`.
- Awaiting user front-end verification before cleanup of debug instrumentation and this debug file.
