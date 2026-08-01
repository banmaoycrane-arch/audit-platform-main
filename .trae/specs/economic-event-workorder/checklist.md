# 经济事件工单 — 验收清单

> 对应 [spec.md](./spec.md)  
> 总状态：E0 规格已立 · E1+ 未开工

## E0 规格

- [x] 正式规格写入 `economic-event-workorder/spec.md`
- [x] OS 定义与技术栈写入 `ai-native-finance-os-definition.md`
- [x] 需求域 D14 登记

## E1 事件壳

- [ ] 模型 + Alembic + fix_legacy_db
- [ ] `/api/economic-events` CRUD / 关联 / transition / steps
- [ ] 前端列表 + 详情卡 + 时间轴
- [ ] 分录列表显示所属事件
- [ ] 查询不创建事件（自动化或手工用例）
- [ ] 生产 schema 审计 PASS

## E2 导入聚类

- [ ] 规则聚类建议
- [ ] 人工确认生成事件
- [ ] （可选）LLM 仅命名/类型建议

## E3 Agent

- [ ] Agent 开草稿工单
- [ ] Tool 调用写入 steps
- [ ] 过账前强制人审闸门

## E4 向量

- [ ] event summary 写入 Qdrant（ledger 隔离）
- [ ] 相似事件推荐 UI
