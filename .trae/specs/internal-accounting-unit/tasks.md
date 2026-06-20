# 内部核算单位设计 - 任务分解

## [x] Task 1: 核算单位数据模型设计
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 设计核算单位表（accounting_units）
  - 设计核算单位类型表（accounting_unit_types）
  - 设计核算单位层级关系表（accounting_unit_hierarchy）
  - 设计核算单位组合表（accounting_unit_combinations）
- **Acceptance Criteria Addressed**: FR-1, FR-2, FR-3
- **Test Requirements**:
  - `programmatic` TR-1.1: 数据库表已创建
  - `human-judgment` TR-1.2: 数据模型符合核算单位需求
- **Notes**: 需要支持多类型、层级和组合关系

## [x] Task 2: 跨主体关联设计
- **Priority**: P0
- **Depends On**: Task 1
- **Description**: 
  - 设计核算单位与会计主体的关联表
  - 实现跨主体核算逻辑
- **Acceptance Criteria Addressed**: FR-4
- **Test Requirements**:
  - `programmatic` TR-2.1: 能正确关联核算单位与多个会计主体
  - `programmatic` TR-2.2: 能查询跨主体的核算数据
  - `human-judgment` TR-2.3: 关联逻辑符合业务需求

## [x] Task 3: 动态合并/分离引擎
- **Priority**: P1
- **Depends On**: Task 1
- **Description**: 
  - 实现核算单位的合并操作
  - 实现核算单位的分离操作
  - 记录合并/分离历史
- **Acceptance Criteria Addressed**: FR-5
- **Test Requirements**:
  - `programmatic` TR-3.1: 能合并多个核算单位
  - `programmatic` TR-3.2: 能分离合并的核算单位
  - `human-judgment` TR-3.3: 合并/分离逻辑正确

## [x] Task 4: 语义检索服务
- **Priority**: P1
- **Depends On**: Task 1
- **Description**: 
  - 实现核算单位名称的语义匹配
  - 支持模糊查询和别名映射
- **Acceptance Criteria Addressed**: FR-6
- **Test Requirements**:
  - `programmatic` TR-4.1: 语义匹配准确率≥90%
  - `human-judgment` TR-4.2: 检索结果相关

## [x] Task 5: 版本历史管理
- **Priority**: P1
- **Depends On**: Task 1
- **Description**: 
  - 记录核算单位的历史变化
  - 支持版本追溯
- **Acceptance Criteria Addressed**: FR-7
- **Test Requirements**:
  - `programmatic` TR-5.1: 能记录核算单位变更历史
  - `programmatic` TR-5.2: 能追溯历史版本
  - `human-judgment` TR-5.3: 版本管理逻辑清晰

## [x] Task 6: API 接口开发
- **Priority**: P1
- **Depends On**: Task 2, Task 3, Task 4, Task 5
- **Description**: 
  - 开发核算单位查询接口
  - 开发核算单位合并/分离接口
  - 开发跨主体核算接口
- **Acceptance Criteria Addressed**: FR-1, FR-4, FR-5, FR-6
- **Test Requirements**:
  - `programmatic` TR-6.1: GET /api/accounting-units 返回状态码200
  - `programmatic` TR-6.2: POST /api/accounting-units/merge 返回合并结果
  - `human-judgment` TR-6.3: API 文档清晰

## [x] Task 7: 物料层级数据模型设计
- **Priority**: P0
- **Depends On**: Task 1
- **Description**: 
  - 设计行业表（industry）
  - 设计物料表（material），包含原材料、半成品、成品、SKU类型
  - 设计物料BOM表（material_bom），记录物料组成关系
- **Acceptance Criteria Addressed**: FR-8, FR-10
- **Test Requirements**:
  - `programmatic` TR-7.1: 数据库表已创建
  - `human-judgment` TR-7.2: 数据模型支持物料层级管理
- **Notes**: 物料类型包括：raw_material（原材料）、semi_finished（半成品）、finished（成品）、sku（商品SKU）

## [x] Task 8: 行业颗粒度推荐服务
- **Priority**: P1
- **Depends On**: Task 7
- **Description**: 
  - 实现行业推荐颗粒度配置
  - 根据行业类型推荐核算颗粒度级别
- **Acceptance Criteria Addressed**: FR-9
- **Test Requirements**:
  - `programmatic` TR-8.1: 能根据行业返回推荐颗粒度
  - `human-judgment` TR-8.2: 推荐颗粒度符合行业特点

## [x] Task 9: 物料BOM管理服务
- **Priority**: P1
- **Depends On**: Task 7
- **Description**: 
  - 实现物料BOM的创建和维护
  - 支持多层BOM查询
- **Acceptance Criteria Addressed**: FR-10
- **Test Requirements**:
  - `programmatic` TR-9.1: 能创建多层BOM关系
  - `programmatic` TR-9.2: 能查询物料的完整BOM结构
  - `human-judgment` TR-9.3: BOM管理逻辑正确

## [x] Task 10: API 接口开发（物料管理）
- **Priority**: P1
- **Depends On**: Task 8, Task 9
- **Description**: 
  - 开发物料查询接口
  - 开发BOM管理接口
  - 开发行业颗粒度推荐接口
- **Acceptance Criteria Addressed**: FR-8, FR-9, FR-10
- **Test Requirements**:
  - `programmatic` TR-10.1: GET /api/materials 返回物料列表
  - `programmatic` TR-10.2: GET /api/materials/{id}/bom 返回BOM结构
  - `human-judgment` TR-10.3: API文档清晰

## [x] Task 11: 测试与验证
- **Priority**: P2
- **Depends On**: Task 6, Task 10
- **Description**: 
  - 编写单元测试
  - 编写集成测试
  - 验证核算单位功能完整性
- **Acceptance Criteria Addressed**: 所有FR
- **Test Requirements**:
  - `programmatic` TR-11.1: 单元测试覆盖率≥80%
  - `programmatic` TR-11.2: 集成测试通过
  - `human-judgment` TR-11.3: 测试用例覆盖主要场景

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 1
- Task 4 depends on Task 1
- Task 5 depends on Task 1
- Task 6 depends on Task 2, Task 3, Task 4, Task 5
- Task 7 depends on Task 1
- Task 8 depends on Task 7
- Task 9 depends on Task 7
- Task 10 depends on Task 8, Task 9
- Task 11 depends on Task 6, Task 10