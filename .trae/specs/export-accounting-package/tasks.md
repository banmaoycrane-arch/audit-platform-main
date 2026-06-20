# Tasks

- [x] Task 1: 后端导出 API
  - [x] SubTask 1.1: 新增 `routes_export.py`，提供 `GET /api/import-jobs/{job_id}/export?format=xlsx|csv|json`
  - [x] SubTask 1.2: 不存在 404；不支持格式 400
  - [x] SubTask 1.3: 列：凭证号、行号、日期、科目代码、科目名称、摘要、借方金额、贷方金额、对方单位
  - [x] SubTask 1.4: 在 `main.py` 注册路由

- [x] Task 2: 前端真实下载
  - [x] SubTask 2.1: `client.ts` 增加 `exportImportJob(jobId, format)` 返回 Blob
  - [x] SubTask 2.2: Step5 通过 URL `?jobId=` 拿上下文；缺失则禁用导出按钮并提示
  - [x] SubTask 2.3: 调用真实 API，触发 `URL.createObjectURL` + `<a download>` 下载
  - [x] SubTask 2.4: 移除 XML 选项

- [x] Task 3: 测试与验证
  - [x] SubTask 3.1: 后端测试覆盖：xlsx/csv/json 200、未知 job 404、未知 format 400（test_export_api.py 5 用例）
  - [x] SubTask 3.2: 前端 TypeScript lint 通过
  - [x] SubTask 3.3: 后端全量 pytest 通过（88 passed）

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 1, 2
