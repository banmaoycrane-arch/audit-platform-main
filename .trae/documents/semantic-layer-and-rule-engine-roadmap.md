# 语义层与规则引擎层战略路线图：从结构系统到解释系统

> **文档类型**: 战略规划路线图
> **更新日期**: 2026-07-01
> **文档状态**: 未来规划（非当前执行方案）
> **核心命题**: 财务/审计系统的本质不是“结构系统”，而是“解释系统”。
> **目标**: 通过三大支柱——多准则 Ledger、审计可溯 Entry Graph、审计规则 DSL——将架构从“可存储”升级为“可解释、可验证、可编排”

---

## 一、核心论点：结构系统 vs. 解释系统

### 1.1 当前系统的定位：结构系统

当前系统已经实现了：
- 数据边界清晰（Ledger）
- 协作边界清晰（Team / Project）
- 凭证分录结构完整（Voucher / AccountingEntry）
- 审计工作流模型完整（AuditTask / WorkBranch / ReviewRequest）

但这只是“把数据放对地方”。

### 1.2 财务/审计的真正需求：解释系统

财务和审计的核心问题是：
> **同一笔经济事实，在不同规则下应该如何解释？**

| 规则视角 | 解释目标 | 示例问题 |
|---------|---------|---------|
| 会计准则（IFRS/CAS） | 真实公允反映 | 收入何时确认？ |
| 税务规则 | 纳税义务计算 | 增值税销项何时发生？ |
| 管理会计 | 内部决策支持 | 这个事业部的利润是多少？ |
| 审计规则 | 风险与控制判断 | 这个交易是否异常？ |

因此，系统必须能够：
1. **同时存储多种解释**（多准则并存）
2. **证明每个解释的来源**（审计可溯）
3. **灵活编排审计规则**（规则 DSL）

### 1.3 语义层与规则引擎层的关系

```
┌─────────────────────────────────────────────────────────────────┐
│                     Rule Engine Layer                          │
│  审计规则 DSL → 解析 → 执行 → 输出审计发现/底稿                │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 调用
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Semantic Layer                                │
│  经济事实 → 会计解释 → 税务解释 → 审计解释 → 管理解释        │
│  Mapping Engine / Tax Interpretation / Audit Interpretation     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ 基于
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Fact Layer                                   │
│  Voucher / AccountingEntry / Event / Transaction Source         │
│  可验证的事实链（Audit-proof Graph）                            │
└─────────────────────────────────────────────────────────────────┘
```

**关系说明**:
- **Semantic Layer** 回答“**这是什么意思？**”
- **Rule Engine Layer** 回答“**基于这个意思，应该做什么？**”
- 两者共同把系统从“存数据”升级为“解释数据并行动”

---

## 二、支柱一：多准则 Ledger（Multi-standard Ledger）

### 2.1 设计理念

> **Ledger 不是“唯一账簿”，而是“经济事实的多准则视图层”。**

同一份原始凭证，在不同准则下可能产生不同的分录。

### 2.2 核心模型

```python
class Ledger(Base):
    """逻辑账簿：经济事实的视图容器。"""
    id: int
    name: str
    ledger_type: str  # statutory / tax / management / consolidation
    base_ledger_id: int | None  # 合并/税务账可关联法定账
    accounting_standard: str  # IFRS / CAS / GAAP / tax
    reporting_currency: str
    team_id: int
    organization_id: int | None

class LedgerView(Base):
    """Ledger 视图：定义从事实层到该 Ledger 的转换规则。"""
    id: int
    ledger_id: int
    source_event_type: str  # invoice / payment / contract
    mapping_rule_id: int
    enabled: bool
```

### 2.3 多准则并存的关键机制

| 机制 | 作用 | 示例 |
|------|------|------|
| **Source Event** | 统一记录经济事实 | 一张发票：金额、税率、客户、日期 |
| **Ledger View** | 按准则选择解释规则 | 会计准则确认收入，税务规则确认销项 |
| **Mapping Rule** | 定义事实→分录的转换 | 收入科目、销项税科目、期间归属 |
| **Adjustment Entry** | 记录准则间差异 | 会计收入与税务收入的差异调整 |
| **Reconciliation** | 自动核对跨准则差异 | 会计收入 vs 税务申报差异分析 |

### 2.4 典型场景

**场景：收入确认**

```
经济事实：签订销售合同，交付商品，开具发票，收到款项

会计准则 Ledger（IFRS/CAS）:
  借：应收账款 / 银行存款
  贷：主营业务收入
  贷：应交税费—销项税额

税务 Ledger（VAT）:
  纳税义务发生时间：开票日 / 收款日（孰早）
  销项税额计算：按发票金额 / 1.13 × 13%

管理 Ledger（事业部）:
  按产品线 / 客户区域 / 销售员拆分收入
```

### 2.5 战略价值

- 支持集团审计、跨国企业多准则审计
- 自动产生准则差异调节表
- 税务稽查与会计审计并行
- 为管理决策提供多维度利润视图

---

## 三、支柱二：审计可溯 Entry Graph（Audit-proof Entry Graph）

### 3.1 设计理念

> **每条 AccountingEntry 不是孤立分录，而是可验证的事实链终点。**

### 3.2 核心模型

```python
class AccountingEntry(Base):
    """会计分录：可验证的事实单位。"""
    id: int
    voucher_id: int
    ledger_id: int
    
    # 金额与方向
    debit_amount: Decimal
    credit_amount: Decimal
    account_code: str
    
    # 来源链（audit-proof graph）
    source_event_id: int           # 来源事件（合同/发票/收付款）
    source_event_type: str         # event / source_file / voucher / adjustment
    source_file_id: int | None     # 原始文件证据
    source_document_ids: list[int] | None  # 关联的原始资料清单
    
    # 生成规则
    generation_rule_id: int | None  # 生成的映射规则
    generation_reason: str         # 规则名称 / 人工录入 / AI草稿
    
    # 验证状态
    verification_status: str       # unverified / verified / disputed
    verified_by: int | None        # 验证人
    verified_at: datetime | None   # 验证时间

class SourceEvent(Base):
    """经济事实事件：比凭证更原子的业务发生。"""
    id: int
    event_type: str                # sale / purchase / payment / receipt
    occurred_at: datetime
    counterparty_id: int | None
    contract_id: int | None
    invoice_id: int | None
    payment_id: int | None
    amount: Decimal
    currency: str
    raw_data: dict                 # 原始事件数据快照

class EntryProofEdge(Base):
    """Entry 证明边：记录分录与证据之间的证明关系。"""
    id: int
    entry_id: int
    evidence_type: str             # source_event / source_file / contract / invoice / bank_statement
    evidence_id: int
    edge_type: str                 # generated_from / verified_by / adjusted_from / consolidated_from
    confidence: float              # 证明链可信度
    signature_hash: str | None     # 电子签名哈希
```

### 3.3 可追溯证明链示例

```
contract #1001
    └── invoice #INV-2024-001
            └── payment #PAY-2024-001
                    └── source_event #EVT-001
                            └── accounting_entry #ENTRY-001
                                    └── voucher #VOU-001

Edge 关系：
  ENTRY-001 --generated_from--> EVT-001
  EVT-001 --evidenced_by--> PAY-2024-001
  EVT-001 --evidenced_by--> INV-2024-001
  EVT-001 --derived_from--> contract #1001
  ENTRY-001 --verified_by--> user #5
  VOU-001 --contains--> ENTRY-001
```

### 3.4 关键能力

| 能力 | 说明 | 审计价值 |
|------|------|----------|
| **正向追溯** | 从合同到凭证 | 验证收入确认是否有依据 |
| **反向追溯** | 从凭证到证据 | 发现无来源或来源冲突的分录 |
| **冲突检测** | 同一事件产生矛盾分录 | 识别舞弊或错误 |
| **完整性校验** | 合同金额 = 发票金额 = 收款金额 | 发现收入漏记或虚构 |
| **时间一致性** | 发货日期 ≤ 开票日期 ≤ 入账日期 | 发现提前或延后确认收入 |

### 3.5 战略价值

- 审计师从“抽查凭证”升级为“验证整条交易链”
- 支持智能审计程序自动运行（如收入截止测试）
- 为司法取证和监管检查提供不可抵赖的证据链

---

## 四、支柱三：审计规则 DSL（Audit Rule DSL）

### 4.1 设计理念

> **审计规则不应埋藏在代码中，而应表达为一种可配置、可验证、可共享的“审计语言”。**

类比：
- SQL 是数据库查询的 DSL
- Audit Rule DSL 是审计程序编排的 DSL

### 4.2 目标能力

| 能力 | 说明 |
|------|------|
| **声明式** | 审计人员描述“要查什么”，系统自动执行 |
| **可组合** | 简单规则组合成复杂审计程序 |
| **可追踪** | 每条规则都能解释为什么产生某个发现 |
| **可版本化** | 规则随审计准则更新而版本管理 |
| **可共享** | 行业最佳实践可以沉淀为规则模板 |

### 4.3 DSL 语法设计（示例）

```sql
-- 示例 1：收入截止测试
AUDIT PROCEDURE revenue_cutoff_test
ON ledger @target_ledger
FOR period @audit_period
FILTER account_code IN ('6001', '6051', '6111')  -- 收入类科目
RULES:
  CHECK voucher_date BETWEEN period_start AND period_end
  CHECK source_event.occurred_at <= voucher_date + 3d
  CHECK entry_proof_chain IS COMPLETE
OUTPUT:
  EXCEPTION AS finding WHEN any RULE FAILS
  SEVERITY = 'high'
  AUDIT_AREA = '收入确认'

-- 示例 2：关联方交易识别
AUDIT PROCEDURE related_party_detection
ON ledger @target_ledger
FOR period @audit_period
FILTER counterparty.is_related_party = TRUE
  OR counterparty.name IN control_graph.related_party_list
RULES:
  CHECK amount > materiality_threshold(@project_id)
  CHECK transaction_price BETWEEN market_price_range * 0.8 AND market_price_range * 1.2
OUTPUT:
  EXCEPTION AS finding WHEN amount > threshold AND price OUT OF RANGE
  SEVERITY = 'medium'
  AUDIT_AREA = '关联方交易'

-- 示例 3：抽样测试
AUDIT PROCEDURE sampling_test
ON ledger @target_ledger
FOR population expense_entries
WHERE account_code LIKE '660%'
SAMPLE method = 'monetary_unit_sampling' size = 90 confidence = 95%
OUTPUT:
  SELECTED_ITEMS AS sample_set
```

### 4.4 核心组件

```python
class AuditRule(Base):
    """审计规则：可执行的最小规则单元。"""
    id: int
    name: str
    rule_code: str
    dsl_text: str                    # DSL 源代码
    compiled_expression: str | None  # 编译后的表达式
    version: str
    effective_from: date
    effective_to: date | None
    audit_standard: str              # CAS / IFRS / PCAOB

class AuditProcedure(Base):
    """审计程序：由多个规则组合而成。"""
    id: int
    project_id: int
    ledger_id: int
    procedure_code: str
    name: str
    rule_ids: list[int]
    materiality_threshold: Decimal
    execution_scope: dict            # 期间、科目、业务循环
    schedule: dict | None            # 执行计划

class AuditProcedureRun(Base):
    """审计程序运行实例。"""
    id: int
    procedure_id: int
    branch_id: int | None
    status: str                      # pending / running / completed / failed
    started_at: datetime
    completed_at: datetime | None
    findings_count: int
    execution_log: dict

class AuditFinding(Base):
    """审计发现：规则执行的结果。"""
    id: int
    procedure_run_id: int
    rule_id: int
    severity: str
    title: str
    description: str
    evidence_entry_ids: list[int]    # 关联的分录证据
    status: str                      # open / resolved / confirmed
```

### 4.5 DSL 执行引擎架构

```
DSL Source
    ↓
Lexer & Parser（词法/语法分析）
    ↓
Abstract Syntax Tree (AST)
    ↓
Semantic Analyzer（语义检查）
    ↓
Query Builder（生成 SQL / 向量检索 / 图遍历）
    ↓
Execution Engine（执行审计程序）
    ↓
Result Formatter（输出 findings / 工作底稿）
```

### 4.6 战略价值

- 审计程序从“写死代码”变成“可配置规则”
- 事务所可以沉淀自己的审计方法论
- 行业监管机构可以发布标准审计规则包
- 降低审计师使用技术工具的门槛

---

## 五、三大支柱的关系

```
                    ┌─────────────────────────────┐
                    │   Audit Rule DSL            │
                    │   （规则引擎层）             │
                    │  编排审计程序，输出发现        │
                    └──────────────┬──────────────┘
                                   │
                                   │ 调用解释
                                   ▼
                    ┌─────────────────────────────┐
                    │   Semantic Layer          │
                    │   （语义解释层）             │
                    │  多准则映射、税务解释、审计解释 │
                    └──────────────┬──────────────┘
                                   │
                                   │ 基于事实
                                   ▼
        ┌──────────────────────────────────────────────┐
        │              Audit-proof Entry Graph         │
        │   可验证的交易链：合同 → 发票 → 收付款 → 分录  │
        │   支持正向/反向追溯、完整性校验、冲突检测      │
        └──────────────────────┬───────────────────────┘
                               │
                               ▼
        ┌──────────────────────────────────────────────┐
        │           Multi-standard Ledger               │
        │  法定账 / 税务账 / 管理账 / 合并账 多视图并行  │
        └──────────────────────────────────────────────┘
```

---

## 六、实施路线图

### 阶段 1：基础能力夯实（当前 ~ 3 个月）

**目标**: 完成现有审计范围选择到工作流闭环的端到端链路

| 任务 | 关键动作 |
|------|---------|
| 1.1 | 完成按业务循环审计（by_cycle）的端到端实现 |
| 1.2 | 完成 AuditTask / WorkBranch / ReviewRequest 的 API 和前端接入 |
| 1.3 | 修复数据库迁移版本冲突 |
| 1.4 | 提升测试稳定性，建立核心模块测试基线 |

### 阶段 2：语义层初建（3 ~ 6 个月）

**目标**: 引入 SourceEvent 和 Entry Proof Graph，建立可验证的事实链

| 任务 | 关键动作 |
|------|---------|
| 2.1 | 设计 SourceEvent 数据模型 |
| 2.2 | 在 AccountingEntry 中增加 source_event_id / source_document_ids 等字段 |
| 2.3 | 建立 EntryProofEdge 关系表 |
| 2.4 | 实现从发票/合同/银行流水到分录的自动关联 |
| 2.5 | 提供审计可溯性的前端可视化（如交易链图谱） |

### 阶段 3：多准则 Ledger（6 ~ 9 个月）

**目标**: 支持同一经济事实在多个 Ledger 视图下并行解释

| 任务 | 关键动作 |
|------|---------|
| 3.1 | 扩展 Ledger 类型字段（statutory / tax / management / consolidation） |
| 3.2 | 设计 LedgerView 和 MappingRule 模型 |
| 3.3 | 实现事实→多准则分录的转换引擎 |
| 3.4 | 实现跨 Ledger 差异调节与对账 |
| 3.5 | 支持合并抵消分录自动生成 |

### 阶段 4：规则引擎与 DSL（9 ~ 12 个月）

**目标**: 审计规则可配置、可执行、可沉淀

| 任务 | 关键动作 |
|------|---------|
| 4.1 | 设计 Audit Rule DSL 语法 |
| 4.2 | 实现 DSL 解析器与执行引擎 |
| 4.3 | 建立 AuditRule / AuditProcedure / AuditProcedureRun / AuditFinding 模型 |
| 4.4 | 提供规则模板库（收入截止、关联方、抽样等） |
| 4.5 | 实现规则执行结果与审计工作底稿的自动关联 |

### 阶段 5：Legal Entity + Control Graph（12 ~ 18 个月）

**目标**: 支持复杂集团结构、SPV、VIE、合并审计

| 任务 | 关键动作 |
|------|---------|
| 5.1 | 升级 Organization 为 Legal Entity + Control Graph |
| 5.2 | 实现控制关系图谱模型 |
| 5.3 | 支持基于控制关系的合并范围自动计算 |
| 5.4 | 支持集团层面审计规则统一编排 |

---

## 七、成功标准

| 维度 | 当前状态 | 目标状态 |
|------|---------|---------|
| **数据边界** | ledger_id 单一边界 | 多准则 Ledger 视图 + Control Graph 动态边界 |
| **可追溯性** | 分录→凭证 | 分录→事件→文件→证据链完整可验证 |
| **审计执行** | 代码写死 | 审计规则 DSL 可配置 |
| **行业价值** | 财务 SaaS 工具 | 审计操作系统 + 行业标准潜力 |

---

## 八、关键设计原则

1. **事实层唯一**：同一经济事实只存一次，所有解释都基于它
2. **解释层分离**：会计、税务、审计、管理解释互不污染
3. **规则可验证**：每条规则执行结果必须可解释、可复核
4. **证据不可抵赖**：关键操作和验证必须留痕，支持电子签名
5. **分层渐进**：先跑通端到端，再叠加语义层和规则层

---

## 九、参考文件

- [future-plan-audit-os-multi-entity-kernel.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/future-plan-audit-os-multi-entity-kernel.md) - 未来规划方案
- [current-risks-and-tasks.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/current-risks-and-tasks.md) - 当前风险与任务清单
- [core-business-concepts-boundary.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/core-business-concepts-boundary.md) - 核心业务概念边界
- [audit-github-style-workflow-plan.md](file:///e:/projects/finance-vector-audit/audit-platform-main/.trae/documents/audit-github-style-workflow-plan.md) - 审计工作流规划
- [backend/app/db/models.py](file:///e:/projects/finance-vector-audit/audit-platform-main/backend/app/db/models.py) - 数据模型定义

---

## 十、变更记录

| 日期 | 变更内容 | 更新人 |
|------|----------|--------|
| 2026-07-01 | 初始创建语义层与规则引擎层战略路线图 | AI 助手 |
