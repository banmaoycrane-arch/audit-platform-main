# 经济事件工单 — 验收清单

> 对应 [spec.md](./spec.md)  
> 总状态：E0 规格已立 · E1 事件壳完成 · E2 导入聚类完成 · **E3 Agent / E4 向量已落地（2026-08-02）** · 生产 schema 升到 0034 待运维

## E0 规格

- [x] 正式规格写入 `economic-event-workorder/spec.md`
- [x] OS 定义与技术栈写入 `ai-native-finance-os-definition.md`
- [x] 需求域 D14 登记

## E1 事件壳

- [x] 模型 + Alembic + fix_legacy_db
- [x] `/api/economic-events` CRUD / 关联 / transition / steps
- [x] 查询不创建事件（自动化或手工用例）
- [x] 前端列表 + 详情卡 + 时间轴
- [x] 分录列表显示所属事件（2026-08-01：`AccountingEntryRead` 加 event_id/event_no，凭证展开行显示 E-xxx 并可跳转详情）
- [ ] 生产 schema 审计 PASS（阻塞：生产 stamp 仍 0028，需执行 `deploy/upgrade_prod_alembic_to_0034.sh` 后复验）

## E2 导入聚类

- [x] 规则聚类建议（D1：往来+月份；D2：频率≥2；幂等排除已挂载分录）
- [x] 人工确认生成事件（confirm 后状态推进到 collecting，挂分录+step 日志）
- [x] 前端「从导入生成事件」按钮 + `ClusterSuggestModal`（候选可勾选/编辑标题/显示金额）
- [x] 6/6 后端测试通过（空聚类/正常聚类/频率过滤/confirm 状态推进/幂等/import_job 过滤）
- [ ] （可选）LLM 仅命名/类型建议

## E3 Agent

- [x] Agent 开草稿工单（`create_economic_event_draft`，审批后受控落库，source=agent）
- [x] Tool 调用写入 steps（`agent_tool` step + api_name）
- [x] 过账前强制人审闸门（Agent 禁止 posted/closed；pending_post→posted 仅 user）
- [x] 只读 `list_economic_events` 低风险工具

## E4 向量

- [x] event summary 写入 Qdrant（ledger 隔离；`POST /vector-sync`）
- [x] 相似事件推荐 UI（详情页「相似事件」Tab + `GET /{id}/similar`）
- [x] 无 Qdrant 时优雅降级（不阻断主路径）
