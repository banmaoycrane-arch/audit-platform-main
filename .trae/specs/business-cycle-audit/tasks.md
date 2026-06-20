# 业务循环与审计风险识别 - 任务分解

## [x] Task 1: 业务循环数据模型设计
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 设计业务循环数据模型（采购循环、销售循环、资金循环等）
  - 设计循环状态机（进行中/完成/断裂）
  - 设计循环关联规则配置
- **Acceptance Criteria Addressed**: 业务循环模型定义
- **Test Requirements**:
  - `programmatic` TR-1.1: 数据库表已创建，包含循环类型、状态、关联字段
  - `human-judgment` TR-1.2: 数据模型符合审计业务循环逻辑
- **Notes**: 参考 spec.md 中的业务循环模型设计

## [x] Task 2: 循环关联引擎实现
- **Priority**: P0
- **Depends On**: Task 1
- **Description**: 
  - 实现合同→入库单→发票→付款的关联规则
  - 支持多种业务顺序（先款后货、先票后货等）
  - 实现日期/金额容差配置
- **Acceptance Criteria Addressed**: 循环关联规则
- **Test Requirements**:
  - `programmatic` TR-2.1: 能正确关联合同与入库单（金额容差5%）
  - `programmatic` TR-2.2: 能正确关联入库单与发票（金额容差1%）
  - `human-judgment` TR-2.3: 关联结果符合业务逻辑

## [x] Task 3: 循环断裂检测服务
- **Priority**: P0
- **Depends On**: Task 2
- **Description**: 
  - 实现证据链断裂检测算法
  - 识别四种断裂类型（合同→预付款、预付款→入库、入库→发票、发票→付款）
  - 生成断裂风险标记
- **Acceptance Criteria Addressed**: 循环断裂检测
- **Test Requirements**:
  - `programmatic` TR-3.1: 能检测缺少入库单的断裂情况
  - `programmatic` TR-3.2: 能检测缺少付款证据的断裂情况
  - `human-judgment` TR-3.3: 断裂检测结果准确

## [x] Task 4: 循环后风险分析
- **Priority**: P1
- **Depends On**: Task 3
- **Description**: 
  - 分析循环完成后的风险（预付款未核销、应收账款账龄等）
  - 关联风险到下一循环
- **Acceptance Criteria Addressed**: 风险延伸分析
- **Test Requirements**:
  - `programmatic` TR-4.1: 能识别长期未核销的预付款
  - `programmatic` TR-4.2: 能识别超90天的应收账款
  - `human-judgment` TR-4.3: 风险分析结果合理

## [x] Task 5: API 接口开发
- **Priority**: P1
- **Depends On**: Task 3, Task 4
- **Description**: 
  - 开发业务循环查询接口
  - 开发循环断裂检测接口
  - 开发循环风险分析接口
- **Acceptance Criteria Addressed**: 业务循环 API
- **Test Requirements**:
  - `programmatic` TR-5.1: GET /api/business-cycles 返回状态码200
  - `programmatic` TR-5.2: POST /api/business-cycles/detect-breaks 返回检测结果
  - `human-judgment` TR-5.3: API 文档清晰

## [x] Task 6: 测试与验证
- **Priority**: P2
- **Depends On**: Task 5
- **Description**: 
  - 编写单元测试
  - 编写集成测试
  - 验证业务循环完整性
- **Acceptance Criteria Addressed**: 测试覆盖
- **Test Requirements**:
  - `programmatic` TR-6.1: 单元测试覆盖率≥80%
  - `programmatic` TR-6.2: 集成测试通过
  - `human-judgment` TR-6.3: 测试用例覆盖主要业务场景

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 3
- Task 5 depends on Task 3, Task 4
- Task 6 depends on Task 5