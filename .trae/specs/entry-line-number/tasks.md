# Tasks

- [x] Task 1: 在 `AccountingEntry` 模型中新增 `entry_line_no` 字段及组合索引
  - [x] SubTask 1.1: 在 `backend/app/db/models.py` 中 `AccountingEntry` 增加 `entry_line_no = Column(Integer, nullable=False, default=1)`
  - [x] SubTask 1.2: 增加 `Index("ix_entry_voucher_line", organization_id, voucher_no, entry_line_no)`
  - [x] SubTask 1.3: 旧数据兼容：在创建表时新字段允许为空时回填默认值 `1`

- [x] Task 2: 在导入引擎中分配同凭证内连续行号
  - [x] SubTask 2.1: 在 `import_service.py` 写入分录前，按 `(organization_id, voucher_no)` 分组排序并分配 `entry_line_no`
  - [x] SubTask 2.2: 缺少 `voucher_no` 时默认行号为 1
  - [x] SubTask 2.3: 行号生成不依赖随机 ID，仅依赖解析顺序

- [x] Task 3: API 层暴露 `entry_line_no`
  - [x] SubTask 3.1: `routes_entries.py` 返回结构包含 `entry_line_no`
  - [x] SubTask 3.2: 排序默认按 `(voucher_no, entry_line_no)`

- [x] Task 4: 审计测试与摘要使用行号
  - [x] SubTask 4.1: `routes_audit_tests.py` 在装载凭证证据时使用 `凭证号 + 行号`
  - [x] SubTask 4.2: 摘要库风险描述允许使用行号定位（通过证据 ID 携带）

- [x] Task 5: 前端展示分录行号
  - [x] SubTask 5.1: `EntriesPage` 增加“行号”列展示
  - [x] SubTask 5.2: 前端 `AccountingEntry` 类型补 `entry_line_no`

- [x] Task 6: 后端测试
  - [x] SubTask 6.1: 导入同一凭证多条分录，断言行号为 1..N
  - [x] SubTask 6.2: 不同凭证下行号互不影响
  - [x] SubTask 6.3: 缺失凭证号默认行号为 1

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 1
- Task 4 depends on Task 2 and Task 3
- Task 5 depends on Task 3
- Task 6 depends on Task 1, Task 2, Task 3
