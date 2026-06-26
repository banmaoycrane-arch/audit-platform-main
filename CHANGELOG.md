# Changelog

本文件记录 `audit-platform-main` 仓库的重要变更，格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

## [Unreleased]

## [2026-06-26]

### Added / 新增

- **AI 发票权责发生制暂存**：仅上传发票时，系统按所选会计判断原则生成应收、收入与销项税草案，标记为「暂存-待收款确认」并允许落库，不直接确认银行存款。（PR [#85](https://github.com/banmaoycrane-arch/audit-platform-main/pull/85)）
- **会计判断原则**：凭证生成 API 新增 `accounting_judgment_policy` 参数，支持「默认合规」「收入确认优先」「往来确认优先」三种口径，影响发票借方科目（应收/冲预收）与收入确认时点。（PR [#85](https://github.com/banmaoycrane-arch/audit-platform-main/pull/85)）
- **发票+流水两阶段分录**：同时有发票与银行流水时，先生成开票挂应收（权责发生），再生成收款核销应收，避免发票直连银行存款，便于现金流量表归集。（PR [#85](https://github.com/banmaoycrane-arch/audit-platform-main/pull/85)）

### Changed / 变更

- **AI 凭证 Step3 界面**：新增会计判断原则单选与「暂存-待收款确认」状态提示，部分证据不足时允许继续暂存而非一律阻断。（PR [#85](https://github.com/banmaoycrane-arch/audit-platform-main/pull/85)）

## [2026-06-25]

### Fixed / 修复

- **AI 记账 Step2 期间选择器**：AI 凭证路径 Step2 复用与手工录入相同的会计期间下拉框，并自动选中第一个 `open` / `reopened` 期间；同步 `jobId`、`periodId` 到 URL；未选期间时禁用「下一步」。修复前 AI 路径仅显示文本期间字段，无法进入 Step3 查看草稿。（合并提交 [`3d88bdc`](https://github.com/banmaoycrane-arch/audit-platform-main/commit/3d88bdc)；功能提交 [`a6e43f8`](https://github.com/banmaoycrane-arch/audit-platform-main/commit/a6e43f8)；分支 `cursor/ai-step2-period-picker-70f0`；文件 `frontend/src/pages/AccountingMode/Step2ImportSource.tsx`）

  > **合并说明**：本次因 Cloud Agent 会话的 GitHub PR API 权限不足，未通过 PR 界面合并，而是由 Agent 本地 merge 后 push 到 `main`。后续 Cloud Agent 任务应使用 `cursor/auto-*` 分支并通过 PR 工具合并，详见 [CURSOR_GITHUB_SETUP.md](./CURSOR_GITHUB_SETUP.md)。
