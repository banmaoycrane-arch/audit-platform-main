# AI 原始资料充分性与 Draft 真实流程核验 Spec

## Why
`govern-ai-voucher-evidence-tags` 已标记完成，但仍需要从真实代码和测试角度核验：仅发票、发票+银行流水、仅银行流水等场景是否真的进入正确的 AI draft 或凭证草稿路径。该核验用于确认前端/后端真实链路可用，不重复开发已完成规则。

## What Changes
- 回顾当前角色、代码库和需求状态，确认下一步目标为核验 AI 原始资料充分性规则与 draft 暂存真实链路。
- 读取后端生成分录、证据充分性、draft 暂存、AI 转人工日志相关代码。
- 读取前端 Step3 生成凭证页面，确认资料不足提示、补资料入口、转人工入口是否真实展示。
- 用最小测试补齐真实链路：仅发票进入 draft、发票+流水生成草稿、流水性质不足进入 draft。
- 如发现状态文件已勾选但代码不满足，按最小改动修复。

## Impact
- Affected specs: `govern-ai-voucher-evidence-tags`, `auto-generate-entries-from-source`, `unify-voucher-input-modes`
- Affected code: `backend/app/services/entry_generation_service.py`, 相关 API 路由和测试, `frontend/src/pages/AccountingMode/Step3GenerateEntries.tsx`, `frontend/src/api/client.ts`

## ADDED Requirements
### Requirement: 真实链路核验
系统 SHALL 通过真实后端测试验证资料充分性规则，而不是仅依赖规格勾选状态。

#### Scenario: 仅上传发票
- **WHEN** 导入任务只有发票类原始资料
- **THEN** 系统不应直接生成可落库凭证
- **AND** 系统应返回 draft 状态
- **AND** draft 应提示补充银行流水或收款回单

#### Scenario: 发票与银行流水匹配
- **WHEN** 导入任务同时具备发票和匹配的银行流水/收款回单
- **THEN** 系统可生成待复核凭证草稿
- **AND** 不应提示资料不足

#### Scenario: 银行流水不能证明业务性质
- **WHEN** 导入任务只有银行流水且无法判断业务性质
- **THEN** 系统应返回 draft 状态
- **AND** draft 应提示补充合同、订单或结算单

### Requirement: 前端资料不足提示核验
系统 SHALL 在 Step3 展示资料不足原因和建议动作。

#### Scenario: 前端展示 draft
- **WHEN** 后端返回 draft 状态
- **THEN** 前端显示缺失资料、缺失原因、建议动作
- **AND** 前端提供继续补充资料入口和切换人工录入入口

## MODIFIED Requirements
### Requirement: AI 自动生成凭证验收
AI 自动生成凭证验收 SHALL 包含真实 API/服务测试，确认 draft 暂存、资料补充提示和资料充分时生成草稿三类场景均可运行。

## REMOVED Requirements
无。
