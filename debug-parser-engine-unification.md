# Debug Session: parser-engine-unification

Status: [OPEN]

## Symptom

用户在 `http://127.0.0.1:5173/ledger/vouchers/draft/9` 仍看到文件解析没有采纳 `http://127.0.0.1:5173/parser-engine` 的输出结果，表现为凭证草稿页仍像存在另一套解析模块。

## Expected

整个上传解析流程中，只要涉及文件解析，都统一使用 parser-engine 的通用兼容引擎生成解析结果；`/ledger/vouchers/draft/:jobId` 只消费 parser-engine 结果，不另起解析逻辑。

## Hypotheses

1. `draft/9` 是旧导入任务，数据库里的 `job.draft_data` 仍是旧解析结果，页面展示旧数据，并没有重新走新接口。
2. 实际上传入口没有调用 `/api/import-jobs/{job_id}/files/{file_id}/parse`，而是仍在调用 `/api/import-jobs/{job_id}/process` 或 `/process/sync`。
3. 后端 `/files/{file_id}/parse` 虽已改造，但实际运行的后端进程未重启，仍在执行旧代码。
4. 草稿页读取接口返回的数据结构没有包含 `parser_engine_result`，导致前端回退展示旧的 `file_results` / `contractResult`。
5. parser-engine 页面与导入草稿页上传的是不同文件或不同 job/file 记录，用户看到的是两个独立历史结果。

## Evidence Plan

- 前端：上报上传入口实际调用的接口、草稿页收到的 `draft_data.stage`、是否包含 `parser_engine_result`。
- 后端：上报 `/files/{file_id}/parse`、`/process`、`/process/sync` 哪个接口被实际调用，以及 job/file/draft_data stage。
- 对 `job_id=9` 查询返回结构，判断是否是旧任务数据。

## Changes

- Pending instrumentation only.
