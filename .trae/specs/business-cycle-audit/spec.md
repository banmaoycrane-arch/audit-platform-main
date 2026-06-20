# 业务循环与审计风险识别 - 核心理念

## 1. 设计理念更新

### 1.1 核心洞察

> **"单一业务循环的完结并不意味着没有审计风险，往往应当产生下一个业务循环了。这里一旦业务循环断掉，就意味着审计风险识别刚开始而已。"**

### 1.2 业务循环模型

#### 标准采购业务循环
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        采购业务全生命周期                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   合同签订 ──────→ 预付款项 ──────→ 验收入库 ──────→ 发票结算 ──────→ 付款    │
│      │               │               │               │               │          │
│      │               │               │               │               │          │
│      ↓               ↓               ↓               ↓               ↓          │
│   [合同]         [银行回单]       [入库单]        [发票]         [银行回单]   │
│                                                                             │
│   ╔═══════════════════════════════════════════════════════════════════╗    │
│   ║                    风险识别触发点                                      ║    │
│   ╠═══════════════════════════════════════════════════════════════════╣    │
│   ║  ① 合同 → 预付款中断：可能存在虚假合同                                 ║    │
│   ║  ② 预付款 → 入库中断：可能存在资金占用或虚假采购                      ║    │
│   ║  ③ 入库 → 发票中断：可能存在存货账实不符                              ║    │
│   ║  ④ 发票 → 付款中断：可能存在负债低估                                  ║    │
│   ╚═══════════════════════════════════════════════════════════════════╝    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 业务顺序的灵活性

| 业务类型 | 业务顺序 | 说明 |
|---------|---------|------|
| **标准采购** | 合同 → 入库 → 发票 → 付款 | 先货后票后款 |
| **先款后货** | 合同 → 预款 → 出库 → 开票 | 预付账款模式 |
| **先票后货** | 合同 → 发票 → 入库 → 付款 | 赊销模式 |
| **纯服务** | 合同 → 发票 → 付款 | 无物流环节 |

### 1.3 审计风险识别模型

```
业务循环状态机：

    ┌──────────┐     证据链完整      ┌──────────┐
    │  循环    │ ─────────────────→  │  循环    │
    │  进行中   │                    │  完结    │
    └────┬─────┘                    └────┬─────┘
         │                                 │
         │ 证据链中断                        │
         │ 识别风险点                        │ 完结后产生
         ↓                                 ↓ 新循环风险
    ┌──────────┐                    ┌──────────┐
    │  风险    │                    │  下一    │
    │  标记    │ ─────────────────→ │  循环    │
    └──────────┘   风险延伸到下一循环 └──────────┘
```

## 2. 原始文件解析的稳定性与灵活性

### 2.1 稳定框架（固定部分）

| 文件类型 | 核心字段 | 稳定性 |
|---------|---------|--------|
| **合同** | 合同号、甲乙双方、金额、期限 | ⭐⭐⭐ 高 |
| **入库单/出库单** | 单号、日期、商品、数量、金额、供应商 | ⭐⭐⭐ 高 |
| **物流单据** | 运单号、发货方、收货方、日期 | ⭐⭐ 中 |
| **发票** | 发票号、日期、甲乙双方、税额、金额 | ⭐⭐⭐ 高 |
| **银行回单** | 交易流水号、日期、金额、对方账户 | ⭐⭐⭐ 高 |

### 2.2 灵活映射（自适应部分）

#### 字段别名映射
```python
CONTRACT_FIELD_MAPPING = {
    "合同编号": ["contract_no", "合同号", "contract_number", "合约号"],
    "甲方": ["party_a", "委托方", "甲方", "采购方"],
    "乙方": ["party_b", "受托方", "乙方", "销售方"],
    "合同金额": ["amount", "contract_amount", "总金额", "合同金额"],
    "签订日期": ["sign_date", "签订日期", "日期", "签署日期"],
}

INVOICE_FIELD_MAPPING = {
    "发票号码": ["invoice_no", "invoice_number", "发票号", "票号"],
    "开票日期": ["invoice_date", "开票日期", "日期", "开票日"],
    "购买方": ["buyer", "purchase", "购买方", "购货方", "customer"],
    "销售方": ["seller", "销售方", "vendor", "供应方"],
    "金额": ["amount", "total_amount", "价税合计", "invoice_amount"],
}
```

### 2.3 自适应解析策略

```
┌─────────────────────────────────────────────────────────────┐
│                    自适应解析引擎                             │
├─────────────────────────────────────────────────────────────┤
│  1. 模板匹配层（稳定）                                       │
│     ├─ 标准模板：财务软件导出格式                             │
│     ├─ 行业模板：金蝶/用友/SAP导出格式                       │
│     └─ 自定义模板：用户上传的格式                             │
├─────────────────────────────────────────────────────────────┤
│  2. 智能推断层（灵活）                                       │
│     ├─ 表头语义分析：识别字段含义                            │
│     ├─ 数据类型推断：日期/金额/文本                          │
│     └─ 关联推断：根据金额匹配推断业务关系                     │
├─────────────────────────────────────────────────────────────┤
│  3. 异常处理层                                               │
│     ├─ 缺失字段：标记为"待确认"                             │
│     ├─ 格式错误：尝试标准化转换                             │
│     └─ 无法识别：人工干预标记                                │
└─────────────────────────────────────────────────────────────┘
```

## 3. 业务循环识别引擎

### 3.1 循环关联规则

```python
# 基于关键字段的业务循环关联
LINKING_RULES = {
    # 合同 → 入库单：基于供应商 + 商品 + 金额
    ("contract", "inventory"): {
        "primary_keys": ["supplier", "amount"],
        "secondary_keys": ["product_name", "quantity"],
        "date_tolerance_days": 90,  # 合同签订后90天内入库
        "amount_tolerance": 0.05,   # 5%金额容差
    },
    
    # 入库单 → 发票：基于供应商 + 商品 + 金额
    ("inventory", "invoice"): {
        "primary_keys": ["supplier", "amount"],
        "secondary_keys": ["product_name"],
        "date_tolerance_days": 30,  # 入库后30天内开票
        "amount_tolerance": 0.01,   # 1%金额容差（发票通常精确）
    },
    
    # 发票 → 银行回单：基于金额 + 对方账户
    ("invoice", "bank_statement"): {
        "primary_keys": ["amount", "counterparty"],
        "secondary_keys": [],
        "date_tolerance_days": 60,  # 开票后60天内付款
        "amount_tolerance": 0.01,
    },
}
```

### 3.2 循环断裂检测

```python
class CycleBreakDetector:
    """业务循环断裂检测器"""
    
    def detect_breaks(self, business_cycles: List[BusinessCycle]) -> List[CycleBreak]:
        """
        检测业务循环中的断裂点
        """
        breaks = []
        
        for cycle in business_cycles:
            # 1. 检查每个环节的证据链完整性
            for i in range(len(cycle.steps) - 1):
                current_step = cycle.steps[i]
                next_step = cycle.steps[i + 1]
                
                # 检查时间顺序是否合理
                if not self._check_date_sequence(current_step, next_step):
                    breaks.append(CycleBreak(
                        cycle_id=cycle.id,
                        break_point=i + 1,
                        break_type="date_sequence_error",
                        severity="high",
                        description=f"{current_step.type}日期晚于{next_step.type}日期"
                    ))
                
                # 检查证据链是否断裂
                if not self._check_linkage(current_step, next_step):
                    breaks.append(CycleBreak(
                        cycle_id=cycle.id,
                        break_point=i + 1,
                        break_type="evidence_break",
                        severity="high",
                        description=f"{next_step.type}未见对应{current_step.type}支撑"
                    ))
            
            # 2. 检查循环是否完整闭环
            if not self._check_cycle_completeness(cycle):
                breaks.append(CycleBreak(
                    cycle_id=cycle.id,
                    break_point=len(cycle.steps),
                    break_type="incomplete_cycle",
                    severity="medium",
                    description="业务循环未完整闭环"
                ))
            
            # 3. 检查是否产生新的风险点
            next_cycles = self._find_next_cycles(cycle)
            for next_cycle in next_cycles:
                # 业务循环完结后产生的新风险
                risk = self._analyze_post_cycle_risk(cycle, next_cycle)
                if risk:
                    breaks.append(risk)
        
        return breaks
```

### 3.3 风险延伸到下一循环

```python
# 案例：预付款后无入库
class PostCycleRiskAnalyzer:
    """业务循环完结后的风险分析"""
    
    def analyze(self, completed_cycle: BusinessCycle) -> List[Risk]:
        """
        分析业务循环完结后可能产生的风险
        """
        risks = []
        
        cycle_type = completed_cycle.business_type
        
        # 采购循环完结后的风险
        if cycle_type == "purchase":
            # 检查是否还有预付款未核销
            prepayment = self._find_prepayment(cycle_type)
            if prepayment and not prepayment.linked:
                risks.append(Risk(
                    risk_type="prepayment_uncleared",
                    description=f"预付款{payment.amount}元长期未核销",
                    severity="high",
                    suggestion="核实预付款是否形成损失或被挪用"
                ))
            
            # 检查是否产生新的采购需求
            remaining_contract = self._get_remaining_contract(cycle_type)
            if remaining_contract:
                risks.append(Risk(
                    risk_type="contract_continuation",
                    description=f"合同{contract.no}尚有未执行完毕部分",
                    severity="medium",
                    suggestion="关注合同执行进度和剩余义务"
                ))
        
        # 销售循环完结后的风险
        if cycle_type == "sales":
            # 检查应收账款账龄
            ar = self._find_accounts_receivable(completed_cycle)
            if ar and ar.age_days > 90:
                risks.append(Risk(
                    risk_type="ar_aging",
                    description=f"应收账款{ar.amount}元账龄超过90天",
                    severity="high",
                    suggestion="评估应收账款可收回性，计提坏账准备"
                ))
        
        return risks
```

## 4. 穿行测试的审计逻辑

### 4.1 从证据到凭证的追踪

```
穿行测试路径：

原始文件 ───────────────────────────────────────────────→ 记账凭证
   │                                                          │
   │  ┌──────────────────────────────────────────────────┐    │
   │  │              证据链追踪                            │    │
   │  │                                                  │    │
   │  ├─ 合同 ──→ 确认合同条款 ──→ 付款条款               │    │
   │  ├─ 入库单 ─→ 确认货物验收 ──→ 数量/质量            │    │
   │  ├─ 发票 ───→ 确认债权/债务 ──→ 金额/税率           │    │
   │  └─ 银行回单 → 确认款项收付 ──→ 时间/金额           │    │
   │                                                  │    │
   │  └──────────────────────────────────────────────────┘    │
   │                                                          │
   └──────────────────────────────────────────────────────────┘
                           │
                           ↓
                    汇总审计发现
```

### 4.2 证据充分性评估

```python
class EvidenceSufficiencyEvaluator:
    """审计证据充分性评估"""
    
    EVALUATION_CRITERIA = {
        "contract": {
            "weight": 0.2,  # 权重
            "required_fields": ["contract_no", "amount", "parties"],
            "quality_checks": ["is_signed", "is_stamped", "is_archived"]
        },
        "inventory": {
            "weight": 0.25,
            "required_fields": ["receipt_no", "date", "quantity", "amount"],
            "quality_checks": ["is_signed", "has_warehouse_seal"]
        },
        "invoice": {
            "weight": 0.3,
            "required_fields": ["invoice_no", "date", "amount", "tax"],
            "quality_checks": ["is_validated", "has_chain"]
        },
        "bank_statement": {
            "weight": 0.25,
            "required_fields": ["transaction_no", "date", "amount", "counterparty"],
            "quality_checks": ["is_verified", "has_bank_seal"]
        }
    }
    
    def evaluate(self, evidence_set: List[Evidence]) -> EvaluationResult:
        """
        评估证据充分性
        """
        total_weight = 0
        weighted_score = 0
        
        for evidence in evidence_set:
            criteria = self.EVALUATION_CRITERIA[evidence.type]
            total_weight += criteria["weight"]
            
            # 检查必填字段
            field_score = self._check_required_fields(
                evidence, 
                criteria["required_fields"]
            )
            
            # 检查质量
            quality_score = self._check_quality(
                evidence,
                criteria["quality_checks"]
            )
            
            weighted_score += criteria["weight"] * (field_score * 0.4 + quality_score * 0.6)
        
        final_score = weighted_score / total_weight if total_weight > 0 else 0
        
        return EvaluationResult(
            sufficiency_score=final_score,
            grade=self._score_to_grade(final_score),
            gaps=self._identify_gaps(evidence_set)
        )
```

## 5. 技术实现要点

### 5.1 数据模型

```python
@dataclass
class BusinessCycle:
    """业务循环"""
    id: str
    cycle_type: str  # purchase/sales/expense
    status: str     # in_progress/completed/broken
    
    # 关联的证据
    contract: Evidence = None
    inventory: Evidence = None
    invoice: Evidence = None
    payment: Evidence = None
    
    # 循环状态
    start_date: date
    end_date: date = None
    completeness: float = 0.0  # 0-1
    
    # 风险标记
    risks: List[Risk] = field(default_factory=list)
    breaks: List[CycleBreak] = field(default_factory=list)

@dataclass  
class CycleBreak:
    """循环断裂点"""
    cycle_id: str
    break_point: int
    break_type: str  # evidence_break/date_error/incomplete
    
    severity: str     # high/medium/low
    description: str
    affected_steps: List[str]
    
    # 审计建议
    suggestion: str
    audit_procedure: str
```

### 5.2 解析优先级

| 优先级 | 文件类型 | 解析策略 |
|--------|---------|---------|
| P0 | 发票 | 必须解析，获取金额、日期、甲乙双方 |
| P0 | 银行回单 | 必须解析，获取资金流向证据 |
| P1 | 合同 | 重要参考，确定业务边界和金额 |
| P1 | 入库单/出库单 | 确认货物/服务交付 |
| P2 | 物流单据 | 辅助验证时间线 |
| P2 | 收据 | 补充费用证据 |

## 6. 与现有系统的集成

### 6.1 集成到台账服务

现有 `ledger_service.py` 需扩展：

```python
# 扩展 BusinessFlowDefinition
class BusinessFlowDefinition:
    business_type: BusinessType
    flow_name: str
    
    # 支持多种业务顺序
    possible_sequences: List[List[str]] = [
        ["contract", "prepayment", "inventory", "invoice", "payment"],  # 先款后货
        ["contract", "inventory", "invoice", "payment"],                  # 标准顺序
        ["contract", "invoice", "inventory", "payment"],               # 先票后货
    ]
    
    # 循环断裂风险定义
    break_risks: Dict[str, RiskDefinition]
```

### 6.2 集成到审计测试服务

```python
# 扩展 audit_test_service.py
class AuditTestService:
    def run_cycle_test(self, job_id: int) -> CycleTestReport:
        """
        执行业务循环测试
        """
        # 1. 构建业务循环
        cycles = self._build_business_cycles(job_id)
        
        # 2. 检测循环断裂
        breaks = self._detect_cycle_breaks(cycles)
        
        # 3. 评估证据充分性
        sufficiency = self._evaluate_evidence(cycles)
        
        # 4. 分析循环后风险
        post_risks = self._analyze_post_cycle_risks(cycles)
        
        # 5. 生成审计发现
        findings = self._generate_cycle_findings(breaks, sufficiency, post_risks)
        
        return CycleTestReport(
            cycles=cycles,
            breaks=breaks,
            sufficiency=sufficiency,
            findings=findings
        )
```

## 7. 总结

### 7.1 核心理念

1. **业务循环优先于单一凭证**：审计从业务循环视角出发，而非单个分录
2. **证据链完整性评估**：原始文件是审计证据，需要形成完整证据链
3. **灵活的业务顺序**：支持不同业务模式（先款后货、先票后货等）
4. **风险延伸到下一循环**：循环完结不是终点，而是新风险的起点
5. **循环断裂即风险点**：任何证据链中断都需要审计关注

### 7.2 实现目标

- 稳定：核心文件类型（合同/入库单/发票/银行回单）解析逻辑稳定
- 灵活：支持多种业务顺序和自定义格式
- 可追溯：从原始文件到记账凭证的完整追踪
- 智能：自动识别业务循环和断裂点
- 专业：使用审计准则语言表述风险
