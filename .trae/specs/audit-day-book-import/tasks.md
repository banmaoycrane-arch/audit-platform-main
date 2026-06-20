# Tasks

## Task 1：后端序时簿服务层
- [x] 1.1 新建 `backend/app/services/audit_day_book_service.py`
  - [x] 实现 `process_day_book_import(db, job)` 函数
  - [x] 按 voucher_no 分组，将多行分录合并为凭证
  - [x] 校验每个凭证的借贷平衡（借方合计 == 贷方合计）
  - [x] 检测凭证号连续性，识别跳号
  - [x] 生成检测报告（含跳号列表、不平衡凭证列表）
- [x] 1.2 修改 `backend/app/services/import_service.py`
  - [x] 在 `process_import_job` 中增加 `source_type` 分支判断
  - [x] `audit_day_book` 时调用 `process_day_book_import`
  - [x] `voucher_import` 时保持现有逻辑不变

## Task 2：后端 API 层
- [x] 2.1 修改 `backend/app/api/routes_imports.py`
  - [x] `POST /api/import-jobs` 增加 `source_type` 可选参数（默认 `voucher_import`）
  - [x] 新增 `GET /api/import-jobs/{job_id}/day-book-report` 端点
  - [x] 返回序时簿检测报告（凭证总数、跳号数量、不平衡凭证数量、完整性评分、缺失凭证号列表）
- [x] 2.2 修改 `backend/app/schemas/import_job.py`
  - [x] `ImportJobCreate` 增加 `source_type: str = "voucher_import"`
  - [x] 新增 `DayBookReport` Pydantic 模型

## Task 3：前端序时簿模式接入
- [x] 3.1 修改 `frontend/src/api/client.ts`
  - [x] `createImportJob` 增加 `source_type` 可选参数
  - [x] 新增 `getDayBookReport(jobId)` 方法
- [x] 3.2 修改 `frontend/src/pages/AuditMode/Step3ImportEntries.tsx`
  - [x] 序时簿 Tab 导入时传递 `source_type="audit_day_book"`
  - [x] 序时簿导入完成后，调用 `getDayBookReport` 展示检测报告
  - [x] 在分录表格下方增加序时簿检测报告卡片（跳号、完整性、不平衡凭证）

## Task 4：测试
- [x] 4.1 新建 `backend/tests/test_audit_day_book_api.py`
  - [x] 测试序时簿导入任务创建（source_type 正确存储）
  - [x] 测试序时簿解析与分组（按 voucher_no 合并）
  - [x] 测试借贷平衡校验（不平衡凭证标记异常）
  - [x] 测试跳号检测（连续凭证号 vs 跳号凭证号）
  - [x] 测试检测报告 API 返回正确结构
- [x] 4.2 后端全量测试通过：`python -m pytest backend/tests -q --tb=short --disable-warnings`
- [x] 4.3 前端 lint 通过：`pnpm --dir frontend lint`

## Task 5：文档与收尾
- [x] 5.1 本 spec 的 `tasks.md` 全部勾选
- [x] 5.2 本 spec 的 `checklist.md` 全部勾选

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 1, 2, 3
- Task 5 depends on Task 4
