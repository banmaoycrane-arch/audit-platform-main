# Debug Session: audit-task-create-error

Status: [OPEN]

## Symptom

在 `http://127.0.0.1:5173/audit/tasks` 新建任务填写完毕点击创建时，前端显示“系统处理异常，请联系管理员并提供请求编号”。

## Hypotheses

1. 前端提交的 `ledger_id` 或 `project_id` 类型/值不符合后端 `AuditTaskCreate` schema，导致 422 或统一错误包装。
2. 自动调用项目-账簿关联接口时失败，创建任务仍继续或错误被通用异常提示吞掉。
3. 后端 `audit_task_service.create_task` 校验 `ProjectLedger` 仍未找到关联记录，抛出 `ValueError` 但路由没有转换为 400 响应。
4. `assignee_id` 从输入框以字符串提交，后端期望整数或空值，导致校验失败。
5. 后端创建任务时通知、编号生成或数据库约束异常，前端只显示了统一异常提示。

## Evidence Plan

- 对前端创建任务动作上报 payload、项目账簿关联状态、接口响应。
- 对后端创建任务路由上报收到的 payload、当前用户、异常类型和错误信息。
- 先收集 pre-fix 日志，再做最小修复。

## Changes

- Pending instrumentation only.
