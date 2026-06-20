# Checklist：审计报告导出

- [x] 新增 `backend/app/api/routes_audit_export.py` 提供 xlsx/json 两种导出
- [x] `backend/app/main.py` 已挂载 `audit_export_router`
- [x] 前端 `client.ts` 含 `exportAuditReport(jobId, format)`
- [x] 审计 Step6 移除 setTimeout mock，真实调用导出接口下载 Blob
- [x] 后端 `pytest tests/test_audit_export.py` 4/4 用例通过
- [x] 前端 `npm run lint`（`tsc --noEmit`）通过
