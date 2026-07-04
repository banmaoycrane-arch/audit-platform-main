# 模块依赖规则文档

## 文档版本

- **版本**: v1.0
- **创建日期**: 2025-01-20
- **适用范围**: 财务向量审计系统后端服务层

---

## 一、领域模块定义

### 1.1 模块列表

| 模块名称 | 目录路径 | 业务职责 |
|---------|---------|---------|
| `auth` | `app/services/auth/` | 认证与权限管理 |
| `basic_data` | `app/services/basic_data/` | 基础数据管理（科目、期初、银行、合同） |
| `accounting` | `app/services/accounting/` | 记账闭环（凭证、分录、期间、报表） |
| `audit` | `app/services/audit/` | 审计闭环（任务、底稿、风险、发现） |
| `doc_parsing` | `app/services/doc_parsing/` | 文档解析与向量检索 |
| `agent` | `app/services/agent/` | AI代理与LLM集成 |
| `shared` | `app/services/shared/` | 共享服务（项目、账簿、事务） |

### 1.2 模块职责边界

#### auth（认证与权限）
- 用户登录、注册、密码管理
- JWT令牌生成与验证
- 平台级权限控制
- 不包含业务领域的权限逻辑

#### basic_data（基础数据）
- 科目表管理（COA）
- 期初余额录入与校验
- 会计主体与核算单位管理
- 银行账户与对账
- 合同解析与验证
- 业务循环定义

#### accounting（记账闭环）
- 凭证创建、修改、删除
- 会计分录管理
- 期间状态机（open → pl_transferred → closed）
- 损益结转
- 财务报表生成
- 分录标签与向量服务

#### audit（审计闭环）
- 审计任务创建与分配
- 工作底稿管理
- 风险识别与评估
- 审计发现记录
- 内控测试
- 审计报告生成

#### doc_parsing（文档解析与向量）
- 文件格式识别
- 文档内容解析（规则引擎/LLM引擎）
- OCR识别
- 向量嵌入与存储
- 异步任务管理
- **未来独立扩展候选模块**

#### agent（AI代理）
- LLM客户端封装
- 代理角色注册与调度
- 工具执行与审批流程
- 草稿审核与语义分解

#### shared（共享服务）
- 项目管理
- 账簿管理
- 事务管理
- 数据验证
- 生命周期管理

---

## 二、依赖规则

### 2.1 依赖方向（单向依赖原则）

```
auth ← basic_data ← accounting ← audit
       ↑            ↑            ↑
       └─────────── shared ──────┘
                           ↖
                    doc_parsing ← agent
```

### 2.2 具体依赖规则

| 规则编号 | 规则描述 | 适用场景 |
|---------|---------|---------|
| D01 | **auth 仅被引用，不引用其他模块** | auth 是最底层模块，提供认证能力 |
| D02 | **basic_data 可引用 auth 和 shared** | 基础数据需要认证和共享服务支持 |
| D03 | **accounting 可引用 auth、basic_data、shared** | 记账需要科目、期初等基础数据 |
| D04 | **audit 可引用 auth、basic_data、accounting、shared** | 审计需要访问账簿、凭证、报表 |
| D05 | **doc_parsing 仅引用 shared** | 文档解析是独立域，仅需共享基础设施 |
| D06 | **agent 可引用 shared 和 doc_parsing** | AI代理需要文档解析能力 |
| D07 | **shared 仅引用 auth** | 共享服务需要认证，不依赖业务域 |
| D08 | **禁止跨层跳跃依赖** | 如 audit 不可直接引用 auth，需通过 shared |

### 2.3 禁止的依赖关系

| 禁止依赖 | 原因 |
|---------|-----|
| `auth` → 任何其他模块 | auth 是基础设施，不应依赖业务逻辑 |
| `doc_parsing` → `accounting` | 文档解析应保持独立，便于未来拆分 |
| `doc_parsing` → `audit` | 同上 |
| `agent` → `accounting` | AI代理不应直接操作记账逻辑 |
| `agent` → `audit` | AI代理不应直接操作审计结论 |

---

## 三、接口边界定义

### 3.1 对外暴露的接口协议

#### IDocumentParser（文档解析接口）
```python
class IDocumentParser(Protocol):
    def parse_document(self, file_path: str, file_type: str) -> ParseResult:
        """解析文档，返回结构化结果"""
```

#### IDocumentTagger（文档标签接口）
```python
class IDocumentTagger(Protocol):
    def generate_tags(self, document_id: int, document_type: str) -> list[Tag]:
        """为文档生成语义标签"""
```

#### IEmbeddingService（向量嵌入接口）
```python
class IEmbeddingService(Protocol):
    def embed_text(self, text: str) -> list[float]:
        """将文本转换为向量"""
    
    def batch_embed(self, texts: list[str]) -> list[list[float]]:
        """批量文本向量转换"""
```

#### IProjectService（项目服务接口）
```python
class IProjectService(Protocol):
    def get_project_by_id(self, project_id: int) -> Project:
        """获取项目信息"""
    
    def list_projects_by_team(self, team_id: int) -> list[Project]:
        """获取团队下的项目列表"""
```

#### ILedgerService（账簿服务接口）
```python
class ILedgerService(Protocol):
    def get_ledger_by_id(self, ledger_id: int) -> Ledger:
        """获取账簿信息"""
    
    def list_ledgers_by_project(self, project_id: int) -> list[Ledger]:
        """获取项目下的账簿列表"""
```

### 3.2 未来拆分预留点

#### doc_parsing 模块拆分计划

**拆分时机**：当文档解析任务占系统资源超过 30%，或需要独立扩缩容时。

**拆分方案**：

```
┌─────────────────────────────────────────────────────────┐
│                    当前单体架构                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │  API层   │→│ doc_parsing│→│  数据库   │              │
│  └──────────┘  └──────────┘  └──────────┘              │
└─────────────────────────────────────────────────────────┘
                          ↓ 拆分后
┌─────────────────────────────────────────────────────────┐
│                    拆分后架构                            │
│  ┌──────────┐        ┌──────────────────┐               │
│  │  API层   │──HTTP──│ doc_parsing微服务 │               │
│  └──────────┘        │  (独立部署)       │               │
│                      └──────────────────┘               │
│                               ↓                         │
│                      ┌──────────────────┐               │
│                      │    Qdrant向量库   │               │
│                      └──────────────────┘               │
└─────────────────────────────────────────────────────────┘
```

**拆分步骤**：

1. **阶段1**：定义完整的 gRPC/HTTP 接口契约（当前已完成协议定义）
2. **阶段2**：将 `doc_parsing` 模块封装为独立服务
3. **阶段3**：迁移向量存储到独立 Qdrant 实例
4. **阶段4**：更新 API 层调用方式，支持同步/异步模式

---

## 四、异步处理规则

### 4.1 需要异步处理的场景

| 场景 | 触发条件 | 推荐处理方式 |
|-----|---------|------------|
| 大批量文档解析 | 文件数 > 10 或单文件 > 5MB | 异步任务队列 |
| 向量嵌入 | 文本量 > 1000 段 | 异步批量处理 |
| OCR识别 | 图片数 > 5 张 | 异步并发处理 |
| LLM解析 | 需要调用外部API | 异步任务 + 重试 |
| 审计风险扫描 | 数据量 > 10万条 | 异步批量扫描 |

### 4.2 异步任务状态流转

```
pending → running → completed
     ↓         ↓
   retry    failed
     ↓
  running
```

### 4.3 任务状态定义

| 状态 | 含义 | 操作 |
|-----|-----|-----|
| `pending` | 等待执行 | 可取消、可重试 |
| `running` | 正在执行 | 可查询进度 |
| `completed` | 执行成功 | 获取结果 |
| `failed` | 执行失败 | 查看错误信息 |
| `canceled` | 用户取消 | 终止任务 |

---

## 五、代码引用规范

### 5.1 导入路径规范

**正确写法**：
```python
# 从领域模块导入
from app.services.accounting import VoucherService
from app.services.doc_parsing import DocumentParsingService

# 从共享模块导入
from app.services.shared import ProjectService
```

**错误写法**：
```python
# 禁止直接从子模块导入（除非是协议接口）
from app.services.accounting.voucher_service import VoucherService

# 禁止跨层依赖
from app.services.accounting import AuditTaskService  # audit 的服务不应在 accounting 中
```

### 5.2 协议接口使用规范

**推荐写法**：
```python
from typing import Protocol

class IMyService(Protocol):
    """协议接口定义"""
    def do_something(self) -> None:
        ...

# 使用协议类型注解
def process_with_service(service: IMyService) -> None:
    service.do_something()
```

### 5.3 循环依赖避免

**检测方法**：
- 运行 `python -m app.dependencies_check` 检查循环依赖
- CI/CD 流程中集成依赖检查

**处理策略**：
1. 将公共逻辑提取到 `shared` 模块
2. 使用协议接口进行解耦
3. 通过事件机制实现跨模块通信

---

## 六、变更管理

### 6.1 模块边界变更流程

```
变更申请 → 架构评审 → 影响分析 → 实施变更 → 测试验证 → 文档更新
```

### 6.2 影响分析 checklist

- [ ] 是否违反单向依赖原则
- [ ] 是否需要更新协议接口
- [ ] 是否影响现有 API 兼容性
- [ ] 是否需要数据迁移
- [ ] 是否需要通知下游模块维护者

### 6.3 API 兼容性承诺

- **向后兼容**：新增字段不影响现有调用
- **废弃标记**：移除字段前标记为 deprecated，保留 2 个版本
- **版本控制**：重大变更使用 API 版本号 `v1`, `v2`

---

## 七、附录

### 7.1 模块依赖矩阵

| 引用方\被引用方 | auth | basic_data | accounting | audit | doc_parsing | agent | shared |
|---------------|------|------------|------------|-------|-------------|-------|--------|
| auth | - | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| basic_data | ✅ | - | ❌ | ❌ | ❌ | ❌ | ✅ |
| accounting | ✅ | ✅ | - | ❌ | ❌ | ❌ | ✅ |
| audit | ✅ | ✅ | ✅ | - | ✅ | ❌ | ✅ |
| doc_parsing | ❌ | ❌ | ❌ | ❌ | - | ❌ | ✅ |
| agent | ❌ | ❌ | ❌ | ❌ | ✅ | - | ✅ |
| shared | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | - |

**图例**：
- ✅：允许依赖
- ❌：禁止依赖
- -：自身

### 7.2 关键设计决策记录

| 决策编号 | 决策内容 | 日期 | 原因 |
|---------|---------|------|-----|
| DD001 | doc_parsing 模块保持独立，不依赖业务域 | 2025-01-20 | 为未来独立扩展做准备 |
| DD002 | 使用 Protocol 定义接口边界 | 2025-01-20 | 实现模块解耦，支持依赖注入 |
| DD003 | shared 模块作为唯一跨域依赖点 | 2025-01-20 | 简化依赖管理，减少循环依赖风险 |
| DD004 | 文档解析任务通过数据库表管理状态 | 2025-01-20 | 不引入外部消息队列，降低部署复杂度 |
