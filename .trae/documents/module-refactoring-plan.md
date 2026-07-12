# 财务向量审计系统 - 模块化单体架构重构计划

> **代码真值**: [code-truth-status.md](./code-truth-status.md)  
> **执行状态**: 领域目录 **已于 `99a15db` 提交**；下文 §2.1「扁平结构」描述为 **重构前快照**，仅供对照。

## 一、计划概述

### 1.1 目标
基于微服务架构可行性分析结论，对当前单体架构进行模块化重构，为未来渐进式拆分奠定基础。

### 1.2 核心任务
| 序号 | 任务 | 优先级 | 状态（2026-07-05 代码） |
|------|------|--------|-------------------------|
| 1 | 强化服务层的领域划分 | 高 | ✅ **已完成** — `accounting/` `audit/` `auth/` `agent/` `basic_data/` `doc_parsing/` `shared/` |
| 2 | 建立清晰的模块依赖规则 | 高 | 🔄 **部分** — 见 `module-dependency-rules.md`，import 仍待清理 |
| 3 | 为未来拆分预留接口边界 | 中 | 🔄 **部分** — API 未收敛，见 `api-boundary-governance-plan.md` |
| 4 | 优化文档解析模块的异步处理能力 | 高 | 🔄 **部分** — `doc_parsing/async_parsing_service.py` 已存在 |
| 5 | 清理根目录残留重复服务 | 高 | ⏳ **待做** — `seal_*`、`project_service.py` 等与子包重复 |

### 1.3 核心原则
- **不破坏现有功能**：重构过程中保持所有 API 接口不变
- **渐进式演进**：先建立边界，再逐步迁移
- **预留拆分点**：为文档解析 + 向量检索模块预留独立部署能力

---

## 二、当前架构分析

> **注意**: 本节描述重构**前**结构。当前代码已迁至领域子目录，见 [code-truth-status.md §2.1](./code-truth-status.md)。

### 2.1 现有服务层结构（历史快照 · 重构前）

当前服务层文件列表（50+ 个服务文件）：

**认证与权限**：auth_service.py, platform_permission_service.py
**基础数据**：coa_service.py, counterparty_service.py, opening_balance_service.py, accounting_unit_service.py, entity_management_service.py
**记账闭环**：voucher_service.py, voucher_management_service.py, entry_generation_service.py, entry_query_service.py, entry_delete_service.py, period_close_service.py, accounting_period_service.py, financial_statements_service.py
**审计闭环**：audit_task_service.py, audit_workflow_service.py, audit_review_service.py, audit_test_service.py, audit_report_service.py, risk_analysis_service.py, confirmation_service.py, workpaper_service.py
**文档解析与向量**：document_parsing_service.py, document_tag_service.py, document_tag_indexer.py, document_tag_vector_service.py, unified_import_service.py, import_service.py, import_routing_service.py, parser_engine/*, ocr_service.py, embedding_service.py
**AI 代理**：agent_service.py, agent_orchestration_service.py, agent_tool_execution_service.py, agent_approval_service.py, llm_client_service.py, ai_client_service.py
**通用服务**：project_service.py, ledger_service.py, ledger_management_service.py, team_service.py, lifecycle_service.py, transaction_manager.py, transaction_service.py, data_validator.py, logic_check_service.py

### 2.2 依赖关系分析

**核心依赖链**：
```
auth_service → [所有服务]
project_service → ledger_service → [entry, voucher, period, coa, counterparty]
document_parsing_service → [parser_engine, import_service, document_tag_indexer]
audit_task_service → [project_service, ledger_service, risk_analysis_service]
entry_generation_service → [coa_service, counterparty_service, entity_management_service]
```

**高耦合服务**：
- `document_parsing_service.py` 直接调用 `parser_engine/*` 多个模块
- `unified_import_service.py` 依赖 `import_service.py`, `entry_generation_service.py`, `document_parsing_service.py`
- `agent_orchestration_service.py` 依赖多个业务服务

---

## 三、目标架构设计

### 3.1 领域模块划分

```
backend/app/
├── api/                      # REST API 路由层（保持不变，映射到新服务）
│   ├── routes_*.py           # 路由文件（50+ 个，保持位置不变）
│   └── __init__.py
├── services/                 # 业务逻辑层（领域化重组）
│   ├── __init__.py           # 重导出，保持向后兼容
│   ├── auth/                 # 认证与权限域
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   └── platform_permission_service.py
│   ├── basic_data/           # 基础数据域
│   │   ├── __init__.py
│   │   ├── coa_service.py
│   │   ├── counterparty_service.py
│   │   ├── opening_balance_service.py
│   │   ├── accounting_unit_service.py
│   │   └── entity_management_service.py
│   ├── accounting/           # 记账闭环域
│   │   ├── __init__.py
│   │   ├── voucher_service.py
│   │   ├── voucher_management_service.py
│   │   ├── entry_generation_service.py
│   │   ├── entry_query_service.py
│   │   ├── entry_delete_service.py
│   │   ├── period_close_service.py
│   │   ├── accounting_period_service.py
│   │   └── financial_statements_service.py
│   ├── audit/                # 审计闭环域
│   │   ├── __init__.py
│   │   ├── audit_task_service.py
│   │   ├── audit_workflow_service.py
│   │   ├── audit_review_service.py
│   │   ├── audit_test_service.py
│   │   ├── audit_report_service.py
│   │   ├── risk_analysis_service.py
│   │   ├── confirmation_service.py
│   │   └── workpaper_service.py
│   ├── doc_parsing/          # 文档解析与向量域（优先拆分候选）
│   │   ├── __init__.py
│   │   ├── document_parsing_service.py
│   │   ├── document_tag_service.py
│   │   ├── document_tag_indexer.py
│   │   ├── document_tag_vector_service.py
│   │   ├── unified_import_service.py
│   │   ├── import_service.py
│   │   ├── import_routing_service.py
│   │   ├── ocr_service.py
│   │   ├── embedding_service.py
│   │   └── parser_engine/    # 解析引擎子模块
│   │       ├── __init__.py
│   │       ├── auto_archive_service.py
│   │       ├── config_service.py
│   │       ├── format_recognizer.py
│   │       ├── parse_result.py
│   │       ├── rule_parsers.py
│   │       └── unified_parser_service.py
│   ├── agent/                # AI 代理域
│   │   ├── __init__.py
│   │   ├── agent_service.py
│   │   ├── agent_orchestration_service.py
│   │   ├── agent_tool_execution_service.py
│   │   ├── agent_approval_service.py
│   │   ├── llm_client_service.py
│   │   └── ai_client_service.py
│   └── shared/               # 共享服务（跨域调用）
│       ├── __init__.py
│       ├── project_service.py
│       ├── ledger_service.py
│       ├── ledger_management_service.py
│       ├── team_service.py
│       ├── lifecycle_service.py
│       ├── transaction_manager.py
│       ├── transaction_service.py
│       ├── data_validator.py
│       └── logic_check_service.py
├── models/                   # 数据模型层（保持不变）
├── schemas/                  # 数据传输对象（保持不变）
├── core/                     # 核心基础设施（保持不变）
│   ├── config.py
│   ├── dependencies.py
│   ├── gateway.py
│   └── security.py
└── db/                       # 数据库层（保持不变）
    ├── models.py
    └── session.py
```

### 3.2 模块依赖规则

**规则 1：单向依赖**
- 允许依赖方向：`auth` → `shared` → `basic_data` → `accounting` → `audit`
- 禁止反向依赖：`accounting` 不能直接依赖 `audit`

**规则 2：共享服务优先**
- 跨域服务（project, ledger, team）放入 `shared/` 目录
- 其他域只能通过 `shared/` 访问跨域资源

**规则 3：文档解析域隔离**
- `doc_parsing/` 域对外只暴露标准接口
- 内部实现细节不对外暴露
- 为未来独立部署预留清晰边界

**规则 4：API 层不变**
- 所有路由文件位置不变
- 路由层只做请求/响应转换
- 路由层可调用任意服务层模块

### 3.3 接口边界定义

**未来拆分候选：文档解析服务**

当前调用链：
```
routes_document_parsing.py → document_parsing_service.py → parser_engine/*
                                                              ↓
                                                      ocr_service.py
                                                      embedding_service.py
```

预留接口：
```python
# services/doc_parsing/__init__.py 对外暴露的接口

class IDocumentParser(Protocol):
    """文档解析服务接口（未来独立服务契约）"""
    def parse_document(self, file_path: str, file_type: str) -> ParseResult: ...
    
class IDocumentTagger(Protocol):
    """文档标签服务接口"""
    def generate_tags(self, document_id: int) -> list[DocumentTag]: ...
    
class IEmbeddingService(Protocol):
    """向量嵌入服务接口"""
    def embed_text(self, text: str) -> list[float]: ...
```

---

## 四、实施步骤

### 步骤 1：创建目录结构和重导出层

**目标**：建立领域化目录结构，通过重导出保持向后兼容

**操作**：
1. 创建 7 个领域子目录（auth, basic_data, accounting, audit, doc_parsing, agent, shared）
2. 在每个子目录创建 `__init__.py` 文件
3. 在 `services/__init__.py` 中添加重导出，保持现有导入路径不变
4. 验证所有路由文件的导入是否正常

**文件变更**：
- 创建：`services/auth/__init__.py`
- 创建：`services/basic_data/__init__.py`
- 创建：`services/accounting/__init__.py`
- 创建：`services/audit/__init__.py`
- 创建：`services/doc_parsing/__init__.py`
- 创建：`services/agent/__init__.py`
- 创建：`services/shared/__init__.py`
- 修改：`services/__init__.py`（添加重导出）

**风险**：导入路径变更导致模块找不到
**缓解**：重导出层保持所有原有导入路径不变

### 步骤 2：迁移服务文件到对应领域目录

**目标**：将服务文件按领域分类迁移

**操作**：
1. 按领域分类移动服务文件到对应子目录
2. 更新各文件内部的导入路径
3. 更新路由文件中的导入路径
4. 运行测试验证功能正常

**文件变更**（移动并更新导入）：
- 移动：`auth_service.py` → `services/auth/auth_service.py`
- 移动：`coa_service.py` → `services/basic_data/coa_service.py`
- 移动：`voucher_service.py` → `services/accounting/voucher_service.py`
- 移动：`audit_task_service.py` → `services/audit/audit_task_service.py`
- 移动：`document_parsing_service.py` → `services/doc_parsing/document_parsing_service.py`
- 移动：`agent_service.py` → `services/agent/agent_service.py`
- 移动：`project_service.py` → `services/shared/project_service.py`
- ...（其他服务文件按领域迁移）

**风险**：移动过程中遗漏文件或导入错误
**缓解**：分批次迁移，每批迁移后运行测试

### 步骤 3：定义模块边界协议

**目标**：为关键域边界定义协议接口，作为未来服务契约

**操作**：
1. 在 `services/doc_parsing/__init__.py` 中定义 `IDocumentParser`, `IDocumentTagger`, `IEmbeddingService` 协议
2. 在 `services/shared/__init__.py` 中定义 `IProjectService`, `ILedgerService` 协议
3. 在 `services/accounting/__init__.py` 中定义 `IVoucherService`, `IEntryService` 协议
4. 在 `services/audit/__init__.py` 中定义 `IAuditTaskService`, `IRiskService` 协议

**文件变更**：
- 修改：`services/doc_parsing/__init__.py`（添加协议定义）
- 修改：`services/shared/__init__.py`（添加协议定义）
- 修改：`services/accounting/__init__.py`（添加协议定义）
- 修改：`services/audit/__init__.py`（添加协议定义）

**风险**：协议定义过于复杂，增加维护成本
**缓解**：只定义核心接口，不追求完整覆盖

### 步骤 4：优化文档解析模块异步处理

**目标**：将文档解析过程改为异步处理，提升系统吞吐量

**当前问题**：
- `document_parsing_service.py` 中的解析过程为同步调用
- 大文件解析阻塞请求线程
- 无法并行处理多个解析任务

**优化方案**：

```
用户请求 → routes_document_parsing.py → 创建 ImportJob（同步）
                                           ↓
                                    返回 job_id（立即响应）
                                           ↓
                              [后台任务队列] → document_parsing_service.py（异步）
                                                ↓
                                         parser_engine（并行解析）
                                                ↓
                                         embedding_service（向量生成）
                                                ↓
                                         document_tag_indexer（标签生成）
                                                ↓
                              更新 ImportJob 状态 → WebSocket/SSE 通知前端
```

**操作**：
1. 引入后台任务队列（如 Celery + Redis）
2. 修改 `document_parsing_service.py`，将解析逻辑改为异步任务
3. 添加任务状态查询接口
4. 添加 WebSocket 或 SSE 实时通知机制
5. 修改前端 `ParserVoucherPreview.tsx`，支持异步状态轮询

**文件变更**：
- 创建：`services/doc_parsing/tasks.py`（异步任务定义）
- 修改：`services/doc_parsing/document_parsing_service.py`（添加异步入口）
- 修改：`api/routes_document_parsing.py`（添加任务状态查询接口）
- 修改：`frontend/src/pages/ParserVoucherPreview.tsx`（添加状态轮询）

**风险**：异步任务丢失或重复执行
**缓解**：使用持久化队列，添加任务幂等性校验

### 步骤 5：完善模块依赖文档

**目标**：记录各模块间的依赖关系，便于后续维护和拆分

**操作**：
1. 创建 `backend/app/services/MODULE_DEPENDENCIES.md` 文档
2. 记录每个模块的：
   - 所属领域
   - 核心功能
   - 依赖的其他模块
   - 被其他模块依赖
   - 数据实体所有权
3. 更新 `AGENTS.md`，添加模块依赖规则章节

**文件变更**：
- 创建：`services/MODULE_DEPENDENCIES.md`（模块依赖文档）
- 修改：`AGENTS.md`（添加模块依赖规则）

---

## 五、验证计划

### 5.1 单元测试验证
- 运行所有后端测试：`pnpm test:backend`
- 验证所有服务模块导入正常
- 验证文档解析异步任务执行正确

### 5.2 集成测试验证
- 运行端到端测试：`pnpm test:e2e`
- 验证记账闭环流程正常（凭证录入→审核→过账→报表）
- 验证审计闭环流程正常（任务创建→风险识别→工作底稿）
- 验证文档导入流程正常（上传→解析→标签生成）

### 5.3 性能验证
- 对比重构前后文档解析吞吐量
- 验证异步任务队列正常工作
- 验证大文件上传不阻塞系统

---

## 六、风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 导入路径变更导致功能破坏 | 高 | 严重 | 重导出层保持向后兼容，分批次迁移 |
| 异步任务丢失 | 中 | 中等 | 使用持久化队列，添加任务重试机制 |
| 协议定义过于复杂 | 低 | 低 | 只定义核心接口，不追求完整覆盖 |
| 测试环境数据库冲突 | 中 | 中等 | 使用独立测试数据库，清理测试数据 |

---

## 七、里程碑

| 阶段 | 目标 | 完成标准 |
|------|------|---------|
| L1 目录结构 | 创建领域化目录和重导出层 | 所有导入路径正常 |
| L2 服务迁移 | 完成所有服务文件的领域迁移 | 单元测试通过 |
| L3 接口边界 | 定义核心域边界协议 | 文档完成，接口稳定 |
| L4 异步优化 | 文档解析模块支持异步处理 | 集成测试通过，性能提升 |
| L5 文档完善 | 模块依赖文档和规则更新 | 文档完整，团队共识 |

---

## 八、后续演进路径

### 第一阶段（当前）：模块化单体
- 完成领域化拆分
- 建立模块依赖规则
- 优化文档解析异步处理

### 第二阶段：文档解析服务独立
- 当文档解析日处理量达到 10000+ 份时
- 将 `doc_parsing/` 模块独立为微服务
- 基于已定义的协议接口实现服务间通信

### 第三阶段：AI 代理服务独立
- 当 AI 功能成为核心竞争力时
- 将 `agent/` 模块独立为微服务
- 支持多 LLM 引擎并行调用

### 第四阶段：记账与审计服务独立
- 当团队规模超过 10 人时
- 拆分 `accounting/` 和 `audit/` 模块
- 实现最终一致性数据同步
