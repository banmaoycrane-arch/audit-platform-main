# 会计分期快照与结账反结账 - The Implementation Plan (Decomposed and Prioritized Task List)

## [x] Task 1: 会计分期与快照数据模型设计
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 设计会计期间表，记录组织、期间编码、日期范围、期间类型、状态。
  - 设计期间快照表，记录快照版本、维度、金额、数量、来源范围、状态。
  - 设计结账日志表，记录结账、反结账、快照重建的审计轨迹。
- **Acceptance Criteria Addressed**: AC-1, AC-2, AC-7, AC-9
- **Test Requirements**:
  - `programmatic` TR-1.1: 同一组织内有效会计期间日期不得重叠。
  - `programmatic` TR-1.2: 快照记录包含 period_id、version、dimension_type、amount、snapshot_status。
  - `programmatic` TR-1.3: 结账日志可以记录操作者、原因、事务编号、原状态和新状态。
- **Notes**: 金额字段默认人民币口径，不设计外币字段。

## [x] Task 2: 期间快照生成服务
- **Priority**: P0
- **Depends On**: Task 1
- **Description**: 
  - 实现按会计期间汇总凭证和相关核算维度数据。
  - 支持按会计主体、科目、内部核算单位、项目、部门、产品、SKU、物料等维度生成快照。
  - 支持快照版本号递增和旧版本保留。
- **Acceptance Criteria Addressed**: AC-2, AC-8, AC-9
- **Test Requirements**:
  - `programmatic` TR-2.1: 对同一期间生成快照后，可以查询到有效快照。
  - `programmatic` TR-2.2: 重新生成快照时，新版本号递增，旧版本不被物理删除。
  - `programmatic` TR-2.3: 快照金额按人民币单币种汇总，不触发外币折算逻辑。
- **Notes**: 快照属于缓存层，不替代底层凭证和原始文件。

## [x] Task 3: 快照优先查询机制
- **Priority**: P1
- **Depends On**: Task 2
- **Description**: 
  - 实现期间汇总查询时优先读取有效快照。
  - 当有效快照不存在或已失效时，回退到明细数据计算。
  - 返回结果应标记数据来源为 snapshot 或 live_calculation。
- **Acceptance Criteria Addressed**: AC-3
- **Test Requirements**:
  - `programmatic` TR-3.1: 存在有效快照时，期间汇总返回 source=snapshot。
  - `programmatic` TR-3.2: 快照失效时，期间汇总返回 source=live_calculation。
  - `human-judgement` TR-3.3: 查询结果说明能让财务人员理解数据来自快照还是实时计算。
- **Notes**: 这对性能和结果一致性都很关键。

## [x] Task 4: 结账事务服务
- **Priority**: P0
- **Depends On**: Task 2
- **Description**: 
  - 实现结账操作：检查期间状态、生成最终快照、更新期间状态、记录结账日志。
  - 将结账过程纳入事务管理器，保证原子性。
  - 结账后限制直接修改影响期间快照的数据。
- **Acceptance Criteria Addressed**: AC-4, AC-5, AC-7
- **Test Requirements**:
  - `programmatic` TR-4.1: 结账成功后期间状态为 closed。
  - `programmatic` TR-4.2: 模拟快照生成失败时，期间状态不得变为 closed。
  - `programmatic` TR-4.3: 已结账期间的直接修改被拒绝。
- **Notes**: 财务含义上，结账是期间数据冻结点。

## [x] Task 5: 反结账事务服务
- **Priority**: P0
- **Depends On**: Task 4
- **Description**: 
  - 实现反结账操作：权限检查、原因记录、期间状态恢复、原快照失效、审计日志记录。
  - 反结账过程必须具备事务一致性。
  - 反结账后重新结账时应生成新的快照版本。
- **Acceptance Criteria Addressed**: AC-6, AC-7, AC-9
- **Test Requirements**:
  - `programmatic` TR-5.1: 反结账成功后期间状态为 reopened 或 open。
  - `programmatic` TR-5.2: 原有效快照状态变为 invalidated。
  - `programmatic` TR-5.3: 重新结账后生成新版本快照。
  - `human-judgement` TR-5.4: 反结账日志足以支持审计追溯。
- **Notes**: 反结账应被视为高风险动作，需要保留原因。

## [x] Task 6: API 接口与前端交互约束
- **Priority**: P1
- **Depends On**: Task 3, Task 4, Task 5
- **Description**: 
  - 开发会计期间创建、查询、快照生成、结账、反结账接口。
  - 对已结账期间的数据修改接口增加状态校验。
  - 前端需要明确展示期间状态、快照状态和数据来源。
- **Acceptance Criteria Addressed**: AC-1, AC-3, AC-4, AC-5, AC-6
- **Test Requirements**:
  - `programmatic` TR-6.1: POST /api/accounting-periods 可以创建会计期间。
  - `programmatic` TR-6.2: POST /api/accounting-periods/{id}/close 可以执行结账。
  - `programmatic` TR-6.3: POST /api/accounting-periods/{id}/reopen 可以执行反结账。
  - `human-judgement` TR-6.4: 前端提示能区分 open、closed、reopened 状态。
- **Notes**: API 命名可根据现有路由风格调整。

## [x] Task 7: 测试与验证
- **Priority**: P2
- **Depends On**: Task 6
- **Description**: 
  - 编写会计期间、快照、结账、反结账的单元测试和集成测试。
  - 验证事务失败回滚场景。
  - 验证人民币单币种约束。
- **Acceptance Criteria Addressed**: 所有 AC
- **Test Requirements**:
  - `programmatic` TR-7.1: 会计期间、快照、结账、反结账核心测试通过。
  - `programmatic` TR-7.2: 事务失败时不存在部分有效快照。
  - `human-judgement` TR-7.3: 测试用例覆盖财务常见流程：月结、反月结、重新结账。
- **Notes**: 重点验证事务一致性，而不是复杂成本算法。
