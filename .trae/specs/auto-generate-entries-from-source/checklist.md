# Checklist

- [x] Checkpoint 1: 默认科目库初始化完成（仅一级，约 38 条）
- [x] Checkpoint 2: 会计科目 CRUD API 全部可用，系统科目禁删，被引用的自定义科目禁硬删
- [x] Checkpoint 3: 对方单位档案 CRUD 可用，分录可关联 counterparty_id（模型已加字段）
- [x] Checkpoint 4: EntryTag 关系库写入成功
- [x] Checkpoint 5: EntryTag 向量同步：Qdrant 可用时真实写入；不可用时保留 `vector_pending=true` 降级
- [x] Checkpoint 6: `generate-entries` 必须传 period_id，凭证日期落入期间
- [x] Checkpoint 7: 凭证字推荐规则（银/收/付/工/转/记）正确
- [x] Checkpoint 8: 摘要按规则拼装，不再随机
- [x] Checkpoint 9: 对方单位字段不再硬编码 A 公司/税务局；多行不跨行复制
- [x] Checkpoint 10: `commit-entries` 同时写 entry + tag（向量同步留 pending）
- [x] Checkpoint 11: 前端基础资料页面：[ChartOfAccountsPage](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/BasicData/ChartOfAccountsPage.tsx)、[CounterpartiesPage](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/BasicData/CounterpartiesPage.tsx)、[OpeningBalancesPage](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/pages/BasicData/OpeningBalancesPage.tsx) 在 SAAS Shell 中实施完成，已在侧边栏「基础资料」菜单可达
- [x] Checkpoint 12: 前端 Step2 选择/创建会计期间后通过 URL 带 periodId 到 Step3
- [x] Checkpoint 13: 前端 Step3 真实生成 + 真实提交
- [x] Checkpoint 14: 后端全量 pytest 通过（53 passed）
- [x] Checkpoint 15: 前端 TypeScript lint 通过
