# 原始文件解析引擎与数据库设计 - 任务分解

## [x] Task 1: 数据库表设计与创建
- **Priority**: P0
- **Depends On**: None
- **Description**: 
  - 创建合同主表（contracts）
  - 创建合同当事人表（contract_parties）
  - 创建合同履约义务明细表（contract_performance_obligations）
  - 创建发票表（invoices, invoice_items）
  - 创建入库/出库单表（inventory_documents, inventory_items）
  - 创建银行回单表（bank_statements）
  - 创建企业信息表（companies, company_personnel, related_party_relations）
  - 创建字段别名映射表（field_alias_mappings）
- **Acceptance Criteria Addressed**: 数据库设计
- **Test Requirements**:
  - `programmatic` TR-1.1: 所有数据库表已创建
  - `human-judgment` TR-1.2: 表结构符合设计规范
- **Notes**: 参考 spec.md 中的数据库设计

## [x] Task 2: 字段别名映射引擎
- **Priority**: P0
- **Depends On**: Task 1
- **Description**: 
  - 实现精确匹配
  - 实现模糊匹配（Levenshtein距离）
  - 实现语义匹配（Embedding向量）
  - 实现大模型辅助判断
- **Acceptance Criteria Addressed**: 字段别名映射
- **Test Requirements**:
  - `programmatic` TR-2.1: 精确匹配准确率≥99%
  - `programmatic` TR-2.2: 模糊匹配准确率≥90%
  - `human-judgment` TR-2.3: 映射结果准确

## [x] Task 3: 合同解析引擎（收入准则视角）
- **Priority**: P0
- **Depends On**: Task 2
- **Description**: 
  - 实现收入准则五步法识别
  - 实现履约义务识别引擎
  - 实现交易价格分摊计算
  - 实现收入确认类型判断（时点/时段）
- **Acceptance Criteria Addressed**: 合同解析引擎
- **Test Requirements**:
  - `programmatic` TR-3.1: 能正确识别履约义务
  - `programmatic` TR-3.2: 能正确判断时段/时点履约
  - `human-judgment` TR-3.3: 解析结果符合收入准则

## [x] Task 4: 标签向量化存储
- **Priority**: P1
- **Depends On**: Task 2
- **Description**: 
  - 实现标签生成器（业务类型、风险、关联、时间、金额标签）
  - 实现标签向量化索引器
  - 实现向量检索辅助判断
- **Acceptance Criteria Addressed**: 向量标签存储
- **Test Requirements**:
  - `programmatic` TR-4.1: 标签能正确向量化并存储
  - `programmatic` TR-4.2: 向量检索返回相关结果
  - `human-judgment` TR-4.3: 检索结果相关

## [x] Task 5: 企业信息管理与关联方识别
- **Priority**: P1
- **Depends On**: Task 1
- **Description**: 
  - 实现企业信息查询服务
  - 实现关联方识别引擎
  - 实现关联方交易审计提示
- **Acceptance Criteria Addressed**: 企业信息管理
- **Test Requirements**:
  - `programmatic` TR-5.1: 能正确识别母子公司关系
  - `programmatic` TR-5.2: 能正确识别关键管理人员关联
  - `human-judgment` TR-5.3: 关联方识别结果准确

## [x] Task 6: API 接口开发
- **Priority**: P1
- **Depends On**: Task 3, Task 4, Task 5
- **Description**: 
  - 开发合同解析接口
  - 开发发票解析接口
  - 开发关联方查询接口
  - 开发标签检索接口
- **Acceptance Criteria Addressed**: 解析引擎 API
- **Test Requirements**:
  - `programmatic` TR-6.1: POST /api/parse/contract 返回解析结果
  - `programmatic` TR-6.2: POST /api/parse/invoice 返回解析结果
  - `human-judgment` TR-6.3: API 文档清晰

## [x] Task 7: 测试与验证
- **Priority**: P2
- **Depends On**: Task 6
- **Description**: 
  - 编写单元测试
  - 编写集成测试
  - 验证解析准确性
- **Acceptance Criteria Addressed**: 测试覆盖
- **Test Requirements**:
  - `programmatic` TR-7.1: 单元测试覆盖率≥80%
  - `programmatic` TR-7.2: 集成测试通过
  - `human-judgment` TR-7.3: 测试用例覆盖主要解析场景

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 2
- Task 5 depends on Task 1
- Task 6 depends on Task 3, Task 4, Task 5
- Task 7 depends on Task 6