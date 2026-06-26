# Changelog

本文件记录 `audit-platform-main` 仓库的重要变更，格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

## [Unreleased]

## [2026-06-26]

### Added

- **审计 Step1 范围持久化（Phase A）**：导入任务新增 `audit_scope_type`、`audit_period_id`、`audit_account_codes`、`project_id` 字段；新增 `PUT /api/imports/{job_id}/audit-scope` 接口；审计模式 Step1 支持选择全部/按科目/按期间范围并保存到导入任务，Step2 可读取已保存范围。（PR #83）

## [2026-06-25]

### Fixed / 修复

- **AI 记账 Step2 期间选择器**：AI 凭证路径 Step2 复用与手工录入相同的会计期间下拉框，并自动选中第一个 `open` / `reopened` 期间；同步 `jobId`、`periodId` 到 URL；未选期间时禁用「下一步」。修复前 AI 路径仅显示文本期间字段，无法进入 Step3 查看草稿。（合并提交 [`3d88bdc`](https://github.com/banmaoycrane-arch/audit-platform-main/commit/3d88bdc)；功能提交 [`a6e43f8`](https://github.com/banmaoycrane-arch/audit-platform-main/commit/a6e43f8)；分支 `cursor/ai-step2-period-picker-70f0`；文件 `frontend/src/pages/AccountingMode/Step2ImportSource.tsx`）

  > **合并说明**：本次因 Cloud Agent 会话的 GitHub PR API 权限不足，未通过 PR 界面合并，而是由 Agent 本地 merge 后 push 到 `main`。后续 Cloud Agent 任务应使用 `cursor/auto-*` 分支并通过 PR 工具合并，详见 [CURSOR_GITHUB_SETUP.md](./CURSOR_GITHUB_SETUP.md)。
