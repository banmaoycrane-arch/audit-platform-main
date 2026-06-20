# 审计发现持久化 Spec

## Why

当前审计测试报告与审计发现仅缓存在 `routes_audit_tests.py` 的内存 `_audit_reports` 字典中，应用重启即丢失。审计软件的核心价值是“留痕”，必须把审计发现写入数据库，并对复核动作（确认 / 误报 / 已解决）写入审计动作日志，否则无法支撑合规追溯与会计期间结账冻结。

## What Changes

- 新增数据库表 `audit_findings` 用于持久化每次审计测试的发现条目（与现有 `AuditRisk` 共存，不替换）。
- 新增数据库表 `audit_finding_review_actions` 用于持久化复核动作（处理人、动作、意见、时间）。
- `POST /api/audit-tests/{job_id}/run` 在内存缓存的同时把发现写入 `audit_findings`，每次运行覆盖该 job 的旧发现。
- `GET /api/audit-tests/{job_id}/findings` 优先从数据库读取，内存缓存仅作为运行时加速。
- 新增 `PATCH /api/audit-tests/findings/{finding_id}/review` 用于复核留痕，写入 `audit_finding_review_actions` 并更新 `audit_findings.status`。
- 前端 `Step5ReviewFindings.tsx` 的“批量确认 / 标记误报 / 单条复核”改为调用真实接口。
- 不修改既有 `AuditRisk` 模型；不影响其他规则风险流。

## Impact

- 受影响 specs：
  - `accounting-period-snapshot`：审计发现可作为期间快照的来源
  - `business-cycle-audit`：未来可关联业务循环 ID
  - `audit-step3-real-entries`：完整审计闭环最后一块
- 受影响代码：
  - `backend/app/db/models.py`（新增两张表）
  - `backend/app/api/routes_audit_tests.py`（写库 + 复核接口）
  - `backend/app/schemas/`（如需要新增）
  - `backend/tests/test_audit_tests_api.py`（覆盖持久化与复核）
  - `frontend/src/api/client.ts`（增加复核接口）
  - `frontend/src/pages/AuditMode/Step5ReviewFindings.tsx`（接入真实复核）

## ADDED Requirements

### Requirement: 审计发现持久化

系统 SHALL 在每次执行审计测试时把审计发现写入数据库，确保跨重启可见。

#### Scenario: 运行后落库

- **WHEN** 用户调用 `POST /api/audit-tests/{job_id}/run`
- **THEN** 后端把生成的所有发现写入 `audit_findings`
- **AND** `GET /api/audit-tests/{job_id}/findings` 直接从数据库返回

#### Scenario: 重新运行覆盖旧发现

- **WHEN** 同一 job 再次运行审计测试
- **THEN** 该 job 之前的发现先被删除，再写入新发现，避免重复

### Requirement: 审计发现复核留痕

系统 SHALL 对每次复核动作写入留痕日志，并更新发现状态。

#### Scenario: 复核单条发现

- **WHEN** 用户调用 `PATCH /api/audit-tests/findings/{finding_id}/review`
  且 `action ∈ {confirmed, false_positive, resolved}`
- **THEN** `audit_findings.status` 更新为对应状态
- **AND** `audit_finding_review_actions` 新增一条记录，包含 action、comment、created_at

#### Scenario: 复核未知发现

- **WHEN** finding_id 不存在
- **THEN** 返回 404 且不写入任何记录

## MODIFIED Requirements

### Requirement: `GET /api/audit-tests/{job_id}/findings`

接口 SHALL 优先从数据库返回审计发现；当数据库无该 job 数据时，再从内存缓存读取（兼容首次运行），仍无则返回 404。

## REMOVED Requirements

无。
