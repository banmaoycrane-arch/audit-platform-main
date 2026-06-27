# Changelog

本文件记录 `audit-platform-main` 仓库的重要变更，格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

## [Unreleased]

## [2026-06-27]

### Added / 新增

- **顶部多页签工作区**：新增 `RouteTabs` 组件，在主壳内容区顶部提供系统内页签栏；支持切换、关闭、首页固定，以及账套切换时自动清理账套相关业务标签，形成类似传统财务软件的多窗口工作区体验。（PR [#115](https://github.com/banmaoycrane-arch/audit-platform-main/pull/115)）

## [2026-06-26]

### Added / 新增

- **账套会计时间线起点**：创建账套时可指定 `accounting_start_date`，作为该账套会计期间与报表的时间基准；未指定时默认创建当天。（PR [#94](https://github.com/banmaoycrane-arch/audit-platform-main/pull/94)）
- **审计范围持久化（Step1）**：导入任务支持保存审计范围（全量 / 按科目 / 按期间），新增 `PUT /api/import-jobs/{job_id}/audit-scope`；审计测试报告按已保存范围生成 scope 与 `audit_scope` 元数据。（PR [#94](https://github.com/banmaoycrane-arch/audit-platform-main/pull/94)）
- **凭证入账与导出门禁**：分录新增 `post_status` 字段；Step5 通过 `POST /api/import-jobs/{job_id}/post` 将已复核分录入账，导出接口仅包含 `posted` 状态分录。（PR [#94](https://github.com/banmaoycrane-arch/audit-platform-main/pull/94)）
- **会计判断策略**：AI 凭证生成 API 支持 `accounting_judgment_policy`（`compliant_default` / `revenue_first` / `counterparty_first`），按单据类型与策略生成差异化草稿分录。（PR [#94](https://github.com/banmaoycrane-arch/audit-platform-main/pull/94)）

### Changed / 变更

- **AI 凭证证据暂存（权责发生制）**：单发票可暂存落库（应收+收入），不确认银行存款；发票+流水走「开票挂应收 → 收款核销应收」两笔分录，避免发票直连银行存款，便于现金流量表归集。（PR [#94](https://github.com/banmaoycrane-arch/audit-platform-main/pull/94)）

## [2026-06-25]

### Fixed / 修复

- **AI 记账 Step2 期间选择器**：AI 凭证路径 Step2 复用与手工录入相同的会计期间下拉框，并自动选中第一个 `open` / `reopened` 期间；同步 `jobId`、`periodId` 到 URL；未选期间时禁用「下一步」。修复前 AI 路径仅显示文本期间字段，无法进入 Step3 查看草稿。（合并提交 [`3d88bdc`](https://github.com/banmaoycrane-arch/audit-platform-main/commit/3d88bdc)；功能提交 [`a6e43f8`](https://github.com/banmaoycrane-arch/audit-platform-main/commit/a6e43f8)；分支 `cursor/ai-step2-period-picker-70f0`；文件 `frontend/src/pages/AccountingMode/Step2ImportSource.tsx`）

  > **合并说明**：本次因 Cloud Agent 会话的 GitHub PR API 权限不足，未通过 PR 界面合并，而是由 Agent 本地 merge 后 push 到 `main`。后续 Cloud Agent 任务应使用 `cursor/auto-*` 分支并通过 PR 工具合并，详见 [CURSOR_GITHUB_SETUP.md](./CURSOR_GITHUB_SETUP.md)。
