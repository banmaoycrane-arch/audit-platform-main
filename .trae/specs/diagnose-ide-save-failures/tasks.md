# Tasks

- [x] Task 1: 收集保存失败上下文。
  - [x] SubTask 1.1: 确认近期报错文件：`backend/app/main.py`、`frontend/src/pages/AccountingMode/Step2ImportSource.tsx`、`frontend/src/pages/AuditMode/Step3ImportEntries.tsx`。
  - [x] SubTask 1.2: 检查是否仍存在 `ide临时文件` 目录。
  - [x] SubTask 1.3: 检查项目代码是否引用 `ide临时文件`。

- [x] Task 2: 检查真实文件写入条件。
  - [x] SubTask 2.1: 检查报错文件是否存在、是否只读、所在目录是否可写。
  - [x] SubTask 2.2: 对报错文件所在目录执行临时文件创建和删除测试。
  - [x] SubTask 2.3: 检查是否有开发服务或 Python/Node 进程可能占用文件。
  - [x] SubTask 2.4: 检查 Git 状态，确认是否存在未跟踪临时副本。

- [x] Task 3: 清理临时路径并恢复真实路径。
  - [x] SubTask 3.1: 如 `ide临时文件` 为空或未被引用，清理该目录。
  - [x] SubTask 3.2: 确认真实文件路径可读取。
  - [x] SubTask 3.3: 记录后续只编辑真实路径。

- [x] Task 4: 验证当前功能未受保存失败影响。
  - [x] SubTask 4.1: 运行 `pnpm --dir frontend lint`。
  - [x] SubTask 4.2: 运行必要后端测试或全量后端测试。
  - [x] SubTask 4.3: 更新本规格 tasks.md。
  - [x] SubTask 4.4: 按本次指令不更新 checklist.md，由主代理最终验收。

# Task Dependencies
- Task 2 depends on Task 1.
- Task 3 depends on Task 2.
- Task 4 depends on Task 3.
