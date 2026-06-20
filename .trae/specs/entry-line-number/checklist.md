# Checklist

- [x] Checkpoint 1: `AccountingEntry` 模型已包含 `entry_line_no: int` 字段
- [x] Checkpoint 2: 数据库已创建 `(organization_id, voucher_no, entry_line_no)` 组合索引
- [x] Checkpoint 3: 导入流程能为同一凭证内的多条分录分配 1..N 的连续行号
- [x] Checkpoint 4: 不同凭证号下的行号互不干扰，各自从 1 起
- [x] Checkpoint 5: 缺少 `voucher_no` 时分录的 `entry_line_no` 默认为 1
- [x] Checkpoint 6: `GET /api/entries` 返回结构包含 `entry_line_no`
- [x] Checkpoint 7: 分录默认按 `(voucher_no, entry_line_no)` 排序
- [x] Checkpoint 8: 审计发现描述支持引用“凭证号 + 行号”
- [x] Checkpoint 9: 前端分录列表能展示行号
- [x] Checkpoint 10: 后端单元测试覆盖：同凭证多行号、跨凭证独立、缺失凭证号默认行号
- [x] Checkpoint 11: 本需求已在 `.trae/specs/adaptive-import-engine` 中作为补充被声明（通过本 spec 引用）
