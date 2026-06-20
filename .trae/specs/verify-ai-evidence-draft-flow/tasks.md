# Tasks

- [x] Task 1: 回顾上下文与现有实现。
  - [x] SubTask 1.1: 确认用户和 AI 角色分工。
  - [x] SubTask 1.2: 读取 `govern-ai-voucher-evidence-tags` 和 `auto-generate-entries-from-source` 的完成状态。
  - [x] SubTask 1.3: 读取后端生成分录、资料充分性、draft 暂存、AI 转人工日志相关代码。
  - [x] SubTask 1.4: 读取前端 Step3 页面和 API client。

- [x] Task 2: 核验后端资料充分性真实链路。
  - [x] SubTask 2.1: 测试仅发票时进入 draft，并提示补充银行流水/收款回单。
  - [x] SubTask 2.2: 测试发票与银行流水匹配时生成待复核凭证草稿。
  - [x] SubTask 2.3: 测试仅银行流水且无法判断业务性质时进入 draft，并提示补充合同/订单/结算单。
  - [x] SubTask 2.4: 如测试失败，按最小改动修复服务或 API。

- [x] Task 3: 核验前端 draft 展示。
  - [x] SubTask 3.1: 确认 Step3 能展示缺失资料、缺失原因和建议动作。
  - [x] SubTask 3.2: 确认 Step3 提供继续补充资料入口。
  - [x] SubTask 3.3: 确认 Step3 提供切换人工录入入口。
  - [x] SubTask 3.4: 如前端缺失展示，按最小改动补齐。

- [x] Task 4: 验证与状态同步。
  - [x] SubTask 4.1: 运行相关后端测试。
  - [x] SubTask 4.2: 运行 `pnpm --dir frontend lint`。
  - [x] SubTask 4.3: 更新本规格 tasks.md。
  - [x] SubTask 4.4: 按本次指令不更新 checklist.md，留待主代理最终验收。

# Task Dependencies
- Task 2 depends on Task 1.
- Task 3 depends on Task 1.
- Task 4 depends on Task 2 and Task 3.
