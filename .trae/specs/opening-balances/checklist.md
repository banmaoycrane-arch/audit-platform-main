# Checklist

- [x] Checkpoint 1: `OpeningBalance` 模型存在并具有唯一约束
- [x] Checkpoint 2: `GET /api/opening-balances` 返回该期间所有期初
- [x] Checkpoint 3: `POST /api/opening-balances` 单条 upsert 正确
- [x] Checkpoint 4: 同期同科目重复提交不会新增重复行
- [x] Checkpoint 5: `POST /api/opening-balances/bulk` 批量 upsert 正确
- [x] Checkpoint 6: `DELETE /api/opening-balances/{id}` 正确
- [x] Checkpoint 7: `GET /api/opening-balances/trial-balance` 返回 debit/credit 合计与 is_balanced
- [x] Checkpoint 8: 前端 `/basic/opening-balances` 可访问且能切换期间
- [x] Checkpoint 9: 前端可行内编辑借贷期初并提交
- [x] Checkpoint 10: 前端在不平衡时显示告警
- [x] Checkpoint 11: 后端全量 pytest 通过（58 collected, exit 0）
- [x] Checkpoint 12: 前端 TypeScript lint 通过
