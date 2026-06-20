# Tasks：审计报告导出

## Task 1：编写子 spec 三件套
- [x] 新建 `.trae/specs/audit-report-export/spec.md`
- [x] 新建 `.trae/specs/audit-report-export/tasks.md`（即本文件）
- [x] 新建 `.trae/specs/audit-report-export/checklist.md`

## Task 2：实施
- [x] 后端新增 `backend/app/api/routes_audit_export.py`，提供
      `GET /api/audit-tests/{job_id}/export?format=xlsx|json`
- [x] `backend/app/main.py` 注册 `audit_export_router`
- [x] 前端 `frontend/src/api/client.ts` 新增 `exportAuditReport(jobId, format)`
- [x] 前端 `Step6ExportReport.tsx` 使用 `useSearchParams` 读取 `jobId`，
      移除 PDF/HTML/Word 选项，仅保留 xlsx + json，调用真实导出接口
- [x] 缺失 `jobId` 时 Alert 警告 + 按钮禁用

## Task 3：验证
- [x] 新建 `backend/tests/test_audit_export.py`，覆盖
      xlsx 200 / json 200 / 不支持格式 400 / 任务不存在 404
- [x] `cd backend; pytest tests/test_audit_export.py -v` 通过
- [x] `cd frontend; npm run lint`（即 `tsc --noEmit`）通过

## Task Dependencies

- Task 1 → Task 2 → Task 3 串行
