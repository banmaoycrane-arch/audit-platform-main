# 工作流断点修复记录（2026-06）

用户反馈「很多工作流是断掉的」。经排查，根因集中在以下几类，本轮已优先修复 P0 项。

## 已修复（P0）

### 1. 账簿与组织脱节
- **问题**：每次导入都新建「临时组织」，导致凭证、期间、报表数据彼此对不上。
- **修复**：同一 `ledger_id` 复用唯一 `organization_id`（`ledger_context_service.py`）。

### 2. 步骤导航可跳过校验
- **问题**：`FlowNav` 的「下一步」不检查是否已上传/已保存/已复核，用户会进入空页面。
- **修复**：`FlowNav` 支持 `nextDisabled` / `onNext`；记账 Step2-4、审计 Step2-6 已加门禁。

### 3. 审计 jobId 丢失
- **问题**：审计 Step2 的 `jobId` 只在内存里，点 FlowNav 或刷新后 Step3 无数据。
- **修复**：`jobId` 写入 URL 查询参数，各步骤导航携带 `?jobId=`。

### 4. 报表/期间未按账簿过滤
- **问题**：`PeriodSelector` 拉全库期间，切换账簿后报表仍显示别的组织数据。
- **修复**：`/api/accounting-periods?ledger_id=` + 前端 `PeriodSelector` 传入 `currentLedgerId`。

### 5. 登录后未引导 onboarding
- **问题**：新用户登录直达工作台，但无团队/账簿时后续流程全断。
- **修复**：`resolvePostLoginPath()` — 缺绑定时跳转 `/onboarding` 或 `/onboarding-request`。

### 6. 分录/风险列表未按账簿过滤
- **问题**：`/ledger/entries`、`/risks` 显示全局数据。
- **修复**：API 支持 `ledger_id` 参数，前端按 `currentLedgerId` 查询。

### 7. 无账簿时进入记账/审计被弹回工作台
- **问题**：`LedgerDataGuard` 跳 `/workspace` 形成死循环。
- **修复**：无账簿时跳转 `/onboarding` 或 `/onboarding-request`。

## 仍待完善（P1/P2）

| 项目 | 说明 |
|------|------|
| 工作台 mock 数据 | 总账/审计工作台仍有硬编码统计，需接 `getDashboardSummary` |
| Step4 复核未写回 API | 复核状态仅前端本地，未持久化 |
| 占位模块 | 账簿、总账明细、税务、固定资产等仍为占位页 |
| 组织/人员页 | 无 CRUD API |
| 全局搜索 | MainShell 搜索框未实现 |

请继续按 `financial-acceptance-test-checklist.md` 验收，发现问题请记录模板反馈。
