# Tasks

- [x] Task 1: 修复 `/api/import-jobs/{id}/process/sync` 的响应类型
  - [x] SubTask 1.1: 在 `routes_imports.py` 中移除该端点的 `response_model=ImportJobRead`
  - [x] SubTask 1.2: 调整返回结构为 `{job, report}` 可被 FastAPI 直接序列化

- [x] Task 2: Step3 前端接入真实分录导入流程
  - [x] SubTask 2.1: 移除 `Step3ImportEntries.tsx` 中的 mock 列表
  - [x] SubTask 2.2: 通过 URL `?jobId=` 读取 jobId，未提供时给出警告
  - [x] SubTask 2.3: 实现文件上传组件 → 调用 `/api/import-jobs/{jobId}/files`
  - [x] SubTask 2.4: 调用 `/api/import-jobs/{jobId}/process/sync` 触发解析
  - [x] SubTask 2.5: 调用 `/api/entries?import_job_id={jobId}` 展示真实分录（含 `voucher_no` / `entry_line_no`）
  - [x] SubTask 2.6: 「下一步」按钮带上 `?jobId=`

- [x] Task 3: 前端 API 客户端补齐辅助方法
  - [x] SubTask 3.1: `client.ts` 增加 `processImportJobSync(jobId)`
  - [x] SubTask 3.2: 已有 `uploadFile`、`listEntries` 复用即可

- [x] Task 4: 验证
  - [x] SubTask 4.1: 前端 `pnpm --dir frontend lint` 通过
  - [x] SubTask 4.2: 后端 `python -m pytest backend/tests` 全量通过

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 1
- Task 4 depends on Task 1, 2, 3
