# Checklist

- [x] Checkpoint 1: `/api/import-jobs/{id}/process/sync` 不再因响应类型不匹配返回 500
- [x] Checkpoint 2: Step3 文件上传后，能成功调用真实导入 API（200）
- [x] Checkpoint 3: Step3 调用同步解析后，列表显示真实分录而不是 mock
- [x] Checkpoint 4: Step3 列表显示 `voucher_no` 与 `entry_line_no` 列
- [x] Checkpoint 5: 进入 Step3 时 URL 缺少 jobId 会有提示
- [x] Checkpoint 6: 「下一步」按钮把 `?jobId=` 带到 Step4
- [x] Checkpoint 7: 前端 TypeScript 检查通过
- [x] Checkpoint 8: 后端全量测试通过
