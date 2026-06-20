# 会计主体语义映射设计 - 任务分解

## [x] Task 1: 会计主体数据模型设计
- **Priority**: P0
- **Status**: 完成（entities/entity_tags/entity_scopes/entity_scope_members/entity_versions/virtual_entity_sets/virtual_entity_set_members/entity_relation_types/entity_relations）

## [x] Task 2: 语义映射引擎实现
- **Priority**: P0
- **Status**: 完成（精确名匹配 + 别名/标签 ilike 模糊匹配；进一步的相似度/向量匹配后续在 vector-store 模块继续）

## [x] Task 3: 分录主体标识改造
- **Priority**: P0
- **Status**: 完成（AccountingEntry.original_entity_name 已存在，导入与审计测试均使用该字段）

## [x] Task 4: 合同主体解析增强
- **Priority**: P1
- **Status**: 完成（document_parsing_service 已支持从 extracted_text 解析甲/乙/丙/丁及买卖、采购供应、发承包等多方合同主体，并写入 ContractParty）

## [x] Task 5: 主体范围动态切换引擎
- **Priority**: P1
- **Status**: 完成（EntityScope/EntityScopeMember/VirtualEntitySet 已可用；性能基准延后）

## [x] Task 6: API 接口开发
- **Priority**: P1
- **Status**: 完成
  - POST/GET `/api/entities`
  - GET `/api/entities/search`
  - POST `/api/entities/{id}/tags`
  - GET `/api/entities/{id}/hierarchy`
  - POST/GET `/api/entities/virtual-sets`、`/api/entities/virtual-sets/{id}/members`
  - POST/GET `/api/entities/scopes`、`/api/entities/scopes/{id}/members`
  - POST `/api/entities/detect-confusion`

## [x] Task 7: 测试与验证
- **Priority**: P2
- **Status**: 完成（test_entities_api.py 7 passed；全量后端 39 passed）

# Task Dependencies
- Task 2 depends on Task 1
- Task 3 depends on Task 1
- Task 4 depends on Task 1, Task 2
- Task 5 depends on Task 1, Task 2
- Task 6 depends on Task 2, Task 3, Task 5
- Task 7 depends on Task 6
