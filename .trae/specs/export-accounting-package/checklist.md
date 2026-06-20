# Checklist

- [x] Checkpoint 1: `GET /api/import-jobs/{id}/export?format=xlsx` 返回 200 + 真实 xlsx
- [x] Checkpoint 2: csv / json 也能正常返回
- [x] Checkpoint 3: 未知 job_id 返回 404
- [x] Checkpoint 4: 不支持格式返回 400
- [x] Checkpoint 5: 前端 Step5 缺少 jobId 时禁用导出按钮并提示
- [x] Checkpoint 6: 前端 Step5 点击导出能真实触发浏览器下载
- [x] Checkpoint 7: 前端 XML 选项已移除
- [x] Checkpoint 8: 后端全量 pytest 通过
- [x] Checkpoint 9: 前端 TypeScript lint 通过
