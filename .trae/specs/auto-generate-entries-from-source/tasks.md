# Tasks

- [x] Task 1: 基础资料 - 会计科目模型与默认数据
  - [x] SubTask 1.1: 新增 `ChartOfAccounts` 模型（code/name/parent_code/level/category/direction/is_terminal/status/is_system）
  - [x] SubTask 1.2: 启动时初始化《企业会计准则》一级默认科目（标记 `is_system=true`）；二级语义统一改为 EntryTag

- [x] Task 2: 会计科目 CRUD API
  - [x] SubTask 2.1: `GET /api/coa` 返回列表
  - [x] SubTask 2.2: `POST /api/coa` 新增（code 唯一、parent 必须存在或为空）
  - [x] SubTask 2.3: `PUT /api/coa/{code}` 修改（系统科目允许改名但禁改 code/category）
  - [x] SubTask 2.4: `POST /api/coa/{code}/disable`、`/archive`
  - [x] SubTask 2.5: `DELETE /api/coa/{code}`：仅限非系统、无业务引用

- [x] Task 3: 对方单位档案
  - [x] SubTask 3.1: 新增 `Counterparty` 模型
  - [x] SubTask 3.2: `GET/POST/PUT/disable` API
  - [x] SubTask 3.3: `accounting_entries` 增加 `counterparty_id` 可空 FK，保留旧 `counterparty` 字段

- [x] Task 4: 辅助核算转 Tag（双库）
  - [x] SubTask 4.1: 扩展 `EntryTag` 模型（`tag_type`/`tag_value`/`tag_value_normalized`/`vector_pending`）
  - [x] SubTask 4.2: 在 `entry_generation_service.commit_drafts` 中关系库写入；向量同步留下 `vector_pending=true` 标记，待后续 vector-sync 任务接入 Qdrant
  - [x] SubTask 4.3: 真实 Qdrant 写入与重试；Qdrant 可用时真实写入，不可用时 pending 降级
  - [x] SubTask 4.4: 独立 `GET/POST/DELETE /api/entries/{id}/tags` 与语义搜索

- [x] Task 5: 自动生成分录引擎规则化
  - [x] SubTask 5.1: 新增 `entry_generation_service.py`
  - [x] SubTask 5.2: 凭证字推荐规则（银/收/付/工/转/记）
  - [x] SubTask 5.3: 凭证日期落入会计期间（自动夹紧并打 `date_clamped`）
  - [x] SubTask 5.4: 摘要按规则拼装（凭证字 + 主科目 + 对方单位 + 业务关键词）
  - [x] SubTask 5.5: 对方单位填写规则（多行不复制，未提供留空，不再硬编码税务局）
  - [x] SubTask 5.6: 二级语义提取为 EntryTag 候选（销项/进项/工资/社保/对方单位）

- [x] Task 6: 草稿与落库 API
  - [x] SubTask 6.1: `POST /api/import-jobs/{job_id}/generate-entries`（要 period_id，返回草稿）
  - [x] SubTask 6.2: `POST /api/import-jobs/{job_id}/commit-entries`（落 entry + tag）

- [x] Task 7: 前端 - 基础资料页面
  - [x] SubTask 7.1: `BasicData/ChartOfAccountsPage.tsx`（树状 + CRUD）
  - [x] SubTask 7.2: `BasicData/CounterpartiesPage.tsx`（CRUD）
  - [x] SubTask 7.3: 路由与导航
  - 备注：基础资料页面已在 saas-shell-and-navigation 中作为 SAAS Shell 的一部分实施，路由 `/basic/coa`、`/basic/counterparties`、`/basic/opening-balances` 全部在 [App.tsx](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/App.tsx) 注册，侧边栏导航在 [MainShell.tsx](file:///e:/projects/finance-vector-audit/wroksapce20260616/frontend/src/layout/MainShell.tsx) 显示。

- [x] Task 8: 前端 - 自动生成分录闭环
  - [x] SubTask 8.1: Step2 增加会计期间选择，URL 带 `periodId`
  - [x] SubTask 8.2: Step3 替换 mock，调用 `generate-entries`
  - [x] SubTask 8.3: 复核后调用 `commit-entries`，列表展示真实凭证字号、对方单位、tag

- [x] Task 9: 测试与验证
  - [x] SubTask 9.1: 后端：CoA CRUD、Counterparty CRUD、EntryTag 写入、generate/commit、凭证字规则、期间夹紧（53 passed）
  - [x] SubTask 9.2: 前端 TypeScript lint 通过
  - [x] SubTask 9.3: 后端全量 pytest 通过（53 passed）

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 1
- Task 4 depends on Task 1
- Task 5 depends on Task 1, 3, 4
- Task 6 depends on Task 5
- Task 7 depends on Task 2, 3
- Task 8 depends on Task 6
- Task 9 depends on Task 1–8
