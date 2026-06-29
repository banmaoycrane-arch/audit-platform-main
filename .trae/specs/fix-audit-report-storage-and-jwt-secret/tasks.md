# Tasks

- [x] Task 1: 验证两个安全问题是否真实存在。
  - [x] SubTask 1.1: 读取 `routes_audit_tests.py`，确认 `_audit_reports` 是否被接口写入和读取。
  - [x] SubTask 1.2: 读取 `security.py` 和配置文件，确认 JWT 是否存在默认硬编码密钥回退。
  - [x] SubTask 1.3: 读取相关测试，确认当前接口预期行为。

- [x] Task 2: 将审计报告改为数据库存储。
  - [x] SubTask 2.1: 增加审计报告数据库模型或复用现有报告模型。
  - [x] SubTask 2.2: 生成报告时按导入任务 ID 保存或更新报告。
  - [x] SubTask 2.3: 查询报告时从数据库按导入任务 ID 读取。
  - [x] SubTask 2.4: 移除 `_audit_reports` 全局变量。
  - [x] SubTask 2.5: 为本地 SQLite 增加必要的轻量表结构兼容。

- [x] Task 3: 修复 JWT 默认密钥风险。
  - [x] SubTask 3.1: 在配置中增加 `secret_key` 字段但不提供危险默认值。
  - [x] SubTask 3.2: `create_access_token` 缺少密钥时抛出明确配置错误。
  - [x] SubTask 3.3: `decode_token` 缺少密钥时不使用默认密钥。
  - [x] SubTask 3.4: 移除 `dev-secret-key-do-not-use-in-production` 硬编码回退。
  - [x] SubTask 3.5: 更新测试环境配置，避免测试因缺少密钥误失败。

- [x] Task 4: 增加和更新测试。
  - [x] SubTask 4.1: 测试审计报告生成后可从数据库查询。
  - [x] SubTask 4.2: 测试不同导入任务的审计报告互不串扰。
  - [x] SubTask 4.3: 测试缺少 JWT 密钥时创建令牌失败。
  - [x] SubTask 4.4: 测试配置 JWT 密钥时令牌签发和解析正常。

- [x] Task 5: 运行验证并更新规格状态。
  - [x] SubTask 5.1: 运行审计测试相关后端测试。
  - [x] SubTask 5.2: 运行认证安全相关后端测试。
  - [x] SubTask 5.3: 运行项目要求的前端 lint，确认本次后端安全修复未影响前端。
  - [x] SubTask 5.4: 勾选本规格 `tasks.md`。
  - [x] SubTask 5.5: `checklist.md` 留待主代理验收后更新，本次不修改。

# Task Dependencies
- Task 2 depends on Task 1.
- Task 3 depends on Task 1.
- Task 4 depends on Task 2 and Task 3.
- Task 5 depends on Task 4.

# Final Acceptance Repair Tasks

- [x] Task 6: 修复全量后端测试失败项。
  - [x] SubTask 6.1: 为 `SourceFile` 模型或相关测试数据处理补齐 `ledger_id` 兼容，修复 `TypeError: 'ledger_id' is an invalid keyword argument for SourceFile`。
  - [x] SubTask 6.2: 排查并修复 `backend/tests/test_app.py` 中 `import_jobs` 表结构/迁移不匹配导致的 SQLite OperationalError。
  - [x] SubTask 6.3: 排查并修复 `build_report_payload()` 参数签名与 `test_audit_report_service.py` 预期不一致。
  - [x] SubTask 6.4: 排查并修复 `test_basic_data_api.py` 中 SQLite Date 类型入参错误。
  - [x] SubTask 6.5: 排查并修复 `test_lifecycle.py` 账簿生命周期接口返回 403 的权限或测试上下文问题。

- [x] Task 7: 修复前端 lint 类型错误。
  - [x] SubTask 7.1: 统一 `frontend/src/pages/ProjectsPage.tsx` 与 `frontend/src/api/client` 的 `Project.description` 类型，修复 `string | null | undefined` 不能赋值给 `string | null`。
