# Tasks

- [x] Task 1: 新增审计发现持久化模型
  - [x] SubTask 1.1: 在 `backend/app/db/models.py` 新增 `AuditFinding` 与 `AuditFindingReviewAction` 表
  - [x] SubTask 1.2: 字段满足：finding_id/job_id/finding_type/severity/business_type/finding_title/finding_description/audit_procedure/audit_conclusion/risk_statement/recommendation/related_entries/related_files/metadata/status/created_at
  - [x] SubTask 1.3: 留痕表字段：finding_id/action/comment/created_at

- [x] Task 2: `POST /api/audit-tests/{job_id}/run` 落库
  - [x] SubTask 2.1: 在写入内存缓存的同时把 findings 写入 `audit_findings`
  - [x] SubTask 2.2: 同 job 重新运行时先删除该 job 旧发现再写入新发现
  - [x] SubTask 2.3: 返回结构保持兼容（含 db `id`）

- [x] Task 3: `GET /api/audit-tests/{job_id}/findings` 优先读库
  - [x] SubTask 3.1: 数据库有数据时直接返回
  - [x] SubTask 3.2: 否则回退内存缓存
  - [x] SubTask 3.3: 数据库与内存均无返回 404

- [x] Task 4: 新增复核接口 `PATCH /api/audit-tests/findings/{finding_id}/review`
  - [x] SubTask 4.1: 校验 finding_id 存在；不存在 404
  - [x] SubTask 4.2: 写入 `audit_finding_review_actions`
  - [x] SubTask 4.3: 更新 `audit_findings.status`
  - [x] SubTask 4.4: 返回更新后的发现条目

- [x] Task 5: 前端 Step5 接入真实复核
  - [x] SubTask 5.1: `client.ts` 增加 `reviewAuditFinding(findingId, action, comment)`
  - [x] SubTask 5.2: 单条复核、批量确认、批量误报均调用真实接口
  - [x] SubTask 5.3: `AuditFinding` 字段补 `id` 为字符串/数字兼容；前端使用后端持久化 id

- [x] Task 6: 测试与验证
  - [x] SubTask 6.1: 后端测试覆盖：落库、重跑覆盖、复核留痕、未知 id 404
  - [x] SubTask 6.2: 前端 TypeScript 检查通过
  - [x] SubTask 6.3: 后端全量测试通过

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 1
- Task 5 depends on Task 4
- Task 6 depends on Task 1, 2, 3, 4, 5
