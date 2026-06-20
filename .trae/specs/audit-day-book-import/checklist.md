# Checklist

## 后端服务层
- [x] `audit_day_book_service.py` 存在且实现 `process_day_book_import`
- [x] 按 voucher_no 分组合并凭证逻辑正确
- [x] 借贷平衡校验逻辑正确（不平衡凭证标记异常）
- [x] 跳号检测逻辑正确（识别缺失凭证号）
- [x] `import_service.py` 的 `process_import_job` 增加 source_type 分支

## 后端 API 层
- [x] `POST /api/import-jobs` 支持 `source_type` 参数
- [x] `GET /api/import-jobs/{job_id}/day-book-report` 端点存在
- [x] 序时簿检测报告返回正确结构（凭证总数、跳号数量、不平衡凭证数量、完整性评分、缺失凭证号列表）
- [x] `ImportJobCreate` schema 包含 `source_type`
- [x] `DayBookReport` schema 存在

## 前端
- [x] `client.ts` 的 `createImportJob` 支持 `source_type` 参数
- [x] `client.ts` 包含 `getDayBookReport` 方法
- [x] 序时簿 Tab 导入时传递 `source_type="audit_day_book"`
- [x] 序时簿导入完成后展示检测报告（跳号、完整性、不平衡凭证）

## 测试
- [x] `test_audit_day_book_api.py` 存在且覆盖所有场景
- [x] 后端全量测试通过
- [x] 前端 lint 通过

## 文档
- [x] 本 spec 三件套完整（spec.md / tasks.md / checklist.md）
