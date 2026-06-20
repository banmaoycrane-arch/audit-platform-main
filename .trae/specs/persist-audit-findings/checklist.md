# Checklist

- [x] Checkpoint 1: `audit_findings` 与 `audit_finding_review_actions` 表已创建
- [x] Checkpoint 2: `POST /api/audit-tests/{job_id}/run` 在数据库中可见对应发现条目
- [x] Checkpoint 3: 同一 job 重跑后旧发现被覆盖
- [x] Checkpoint 4: `GET /api/audit-tests/{job_id}/findings` 数据库优先返回
- [x] Checkpoint 5: `PATCH /api/audit-tests/findings/{finding_id}/review` 写入留痕
- [x] Checkpoint 6: 复核后发现状态正确更新
- [x] Checkpoint 7: 未知 finding_id 返回 404
- [x] Checkpoint 8: 前端 Step5 单条/批量复核调用真实接口
- [x] Checkpoint 9: 前端 TypeScript 检查通过
- [x] Checkpoint 10: 后端全量测试通过
