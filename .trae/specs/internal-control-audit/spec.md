# 风险导向审计与内控测试集成

## 1. 设计理念

### 1.1 审计方法论基础

**风险导向审计流程**：
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    风险导向审计方法论                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────┐                                                       │
│   │   了解被审计单位   │                                                      │
│   │   及行业特点      │                                                      │
│   └────────┬────────┘                                                       │
│            │                                                                │
│            ↓                                                                │
│   ┌─────────────────┐                                                       │
│   │   了解内部控制    │ ◄── 内控测试（必须的前置步骤）                        │
│   │   设计与运行     │                                                      │
│   └────────┬────────┘                                                       │
│            │                                                                │
│            ↓                                                                │
│   ┌─────────────────┐                                                       │
│   │   评估重大错报   │                                                      │
│   │   风险水平       │                                                      │
│   └────────┬────────┘                                                       │
│            │                                                                │
│            ↓                                                                │
│   ┌─────────────────┐                                                       │
│   │   确定应对措施   │                                                      │
│   │   设计与执行     │                                                      │
│   └────────┬────────┘                                                       │
│            │                                                                │
│            ↓                                                                │
│   ┌─────────────────┐                                                       │
│   │   获取审计证据   │                                                       │
│   │   形成审计结论   │                                                       │
│   └─────────────────┘                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 核心洞察

> **"客户的内控很多时候是一种熟练但没有形成文档"**

**问题**：
- 内控是审计的重要前提，但客户往往没有文档化
- 内控缺失文档 ≠ 内控不存在
- 需要从实际业务证据中推断内控执行情况

**解决方案**：
- 建立基于行业的**默认内控程序库**
- 从业务证据中检测内控执行痕迹
- 当证据与默认程序不符时，触发预警

## 2. 行业默认内控程序库

### 2.1 内控程序模板结构

```python
class InternalControlProcedure:
    """内部控制系统"""
    
    id: str                           # 程序编号
    control_type: str                 # 控制类型：预防性/检查性/纠正性
    control_category: str             # 控制类别：授权/职责分离/审批/核对/保管
    
    # 内控描述
    description: str                  # "采购需经总经理审批"
    objective: str                   # 控制目标："防止未经授权采购"
    
    # 触发条件
    trigger_conditions: List[str]    # ["采购金额>10000"]
    
    # 证据要求
    evidence_required: List[str]      # ["审批单", "采购合同"]
    evidence_formats: List[str]      # ["签字文件", "电子审批记录"]
    
    # 频率要求
    frequency: str                   # "每笔" / "每日" / "每月"
    
    # 行业适用性
    industries: List[str]            # ["制造业", "商贸业"]
    company_size: str                 # "大型" / "中型" / "小型"
    
    # 风险关联
    risk_category: str              # "采购风险" / "销售风险" / "资金风险"
    inherent_risk: str              # 固有风险：high/medium/low
    control_risk: str               # 控制风险：high/medium/low
```

### 2.2 采购业务内控程序库

```python
PURCHASE_CONTROLS = {
    # 采购申请与审批
    "PC-001": {
        "name": "采购申请审批控制",
        "control_type": "预防性",
        "control_category": "授权",
        "description": "采购申请需经部门经理审批，超过一定金额需总经理审批",
        "trigger_conditions": [
            "采购申请金额 > 5000: 部门经理审批",
            "采购申请金额 > 50000: 总经理审批",
        ],
        "evidence_required": ["采购申请表", "审批签字记录"],
        "frequency": "每笔",
        "risk_level": "high",
    },
    
    # 供应商选择
    "PC-002": {
        "name": "供应商比价控制",
        "control_type": "预防性",
        "control_category": "审批",
        "description": "大额采购需进行供应商比价，保留比价记录",
        "trigger_conditions": [
            "采购金额 > 10000: 需比价",
            "采购金额 > 50000: 需3家以上比价",
        ],
        "evidence_required": ["比价表", "供应商资质文件"],
        "frequency": "每笔",
        "risk_level": "medium",
    },
    
    # 验收控制
    "PC-003": {
        "name": "采购验收控制",
        "control_type": "检查性",
        "control_category": "核对",
        "description": "采购入库需经仓库人员验收，核对数量和规格",
        "trigger_conditions": ["所有采购入库"],
        "evidence_required": ["入库单", "验收签字"],
        "frequency": "每笔",
        "risk_level": "high",
    },
    
    # 付款审批
    "PC-004": {
        "name": "付款审批控制",
        "control_type": "预防性",
        "control_category": "授权",
        "description": "付款需经财务经理和总经理双重审批",
        "trigger_conditions": ["所有付款申请"],
        "evidence_required": ["付款审批单", "银行回单"],
        "frequency": "每笔",
        "risk_level": "high",
    },
    
    # 合同管理
    "PC-005": {
        "name": "合同管理控制",
        "control_type": "预防性",
        "control_category": "保管",
        "description": "采购合同需经法务审核，统一归档管理",
        "trigger_conditions": ["合同金额 > 10000"],
        "evidence_required": ["合同文本", "法务审核记录"],
        "frequency": "每笔",
        "risk_level": "medium",
    },
}
```

### 2.3 销售业务内控程序库

```python
SALES_CONTROLS = {
    "SC-001": {
        "name": "销售订单审批控制",
        "control_type": "预防性",
        "control_category": "授权",
        "description": "销售订单需经销售经理审批，信用客户需评估信用额度",
        "trigger_conditions": [
            "所有销售订单",
            "信用销售: 需评估客户信用",
        ],
        "evidence_required": ["销售订单", "信用评估记录"],
        "frequency": "每笔",
        "risk_level": "high",
    },
    
    "SC-002": {
        "name": "发货控制",
        "control_type": "检查性",
        "control_category": "核对",
        "description": "发货需核对销售订单和客户验收单",
        "trigger_conditions": ["所有发货业务"],
        "evidence_required": ["出库单", "客户签收单"],
        "frequency": "每笔",
        "risk_level": "high",
    },
    
    "SC-003": {
        "name": "发票开具控制",
        "control_type": "检查性",
        "control_category": "核对",
        "description": "发票开具需与出库单核对，确保三单一致",
        "trigger_conditions": ["所有销售业务"],
        "evidence_required": ["发票", "出库单", "客户签收单"],
        "frequency": "每笔",
        "risk_level": "high",
    },
    
    "SC-004": {
        "name": "收款控制",
        "control_type": "检查性",
        "control_category": "核对",
        "description": "收款需与合同约定的付款条款核对",
        "trigger_conditions": ["所有收款业务"],
        "evidence_required": ["银行回单", "合同付款条款"],
        "frequency": "每笔",
        "risk_level": "medium",
    },
}
```

### 2.4 资金业务内控程序库

```python
CASH_CONTROLS = {
    "CC-001": {
        "name": "银行余额调节控制",
        "control_type": "检查性",
        "control_category": "核对",
        "description": "每月末编制银行余额调节表，由独立人员复核",
        "trigger_conditions": ["每月末"],
        "evidence_required": ["银行对账单", "银行存款余额调节表"],
        "frequency": "每月",
        "risk_level": "high",
    },
    
    "CC-002": {
        "name": "现金盘点控制",
        "control_type": "检查性",
        "control_category": "核对",
        "description": "每日/每周进行现金盘点，确保账实相符",
        "trigger_conditions": ["每日/每周"],
        "evidence_required": ["现金盘点表"],
        "frequency": "每日/每周",
        "risk_level": "medium",
    },
    
    "CC-003": {
        "name": "大额资金审批控制",
        "control_type": "预防性",
        "control_category": "授权",
        "description": "大额资金支付需经多级审批",
        "trigger_conditions": [
            "付款 > 50000: 财务经理审批",
            "付款 > 200000: 总经理审批",
        ],
        "evidence_required": ["付款审批单"],
        "frequency": "每笔",
        "risk_level": "high",
    },
}
```

## 3. 内控执行检测引擎

### 3.1 检测原理

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    内控执行检测引擎                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   输入：业务证据（合同/发票/入库单/银行回单）                                  │
│                                                                             │
│   ┌─────────────────────────────────────────────────────────────────┐     │
│   │  1. 证据解析层                                                     │     │
│   │     - 提取证据中的关键信息（金额/日期/审批人/签字）                 │     │
│   │     - 识别证据之间的关联关系                                      │     │
│   └─────────────────────────────────────────────────────────────────┘     │
│                              ↓                                              │
│   ┌─────────────────────────────────────────────────────────────────┐     │
│   │  2. 内控匹配层                                                     │     │
│   │     - 匹配适用的内控程序                                          │     │
│   │     - 检查触发条件是否满足                                        │     │
│   │     - 检查必要证据是否存在                                        │     │
│   └─────────────────────────────────────────────────────────────────┘     │
│                              ↓                                              │
│   ┌─────────────────────────────────────────────────────────────────┐     │
│   │  3. 预警生成层                                                     │     │
│   │     - 识别内控缺失项                                              │     │
│   │     - 量化风险级别                                                │     │
│   │     - 生成预警信息                                                │     │
│   └─────────────────────────────────────────────────────────────────┘     │
│                              ↓                                              │
│   输出：内控预警 + 风险量化                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 检测算法

```python
class InternalControlDetector:
    """内控执行检测器"""
    
    def __init__(self, industry: str, company_size: str):
        self.industry = industry
        self.company_size = company_size
        # 加载适用的内控程序
        self.controls = self._load_applicable_controls()
    
    def detect(self, business_evidence: List[BusinessEvidence]) -> List[ControlAlert]:
        """
        检测内控执行情况
        """
        alerts = []
        
        # 按业务类型分组证据
        evidence_by_type = self._group_evidence(business_evidence)
        
        # 对每类业务检测内控
        for business_type, evidence_list in evidence_by_type.items():
            controls = self._get_controls_for_business(business_type)
            
            for control_id, control in controls.items():
                # 检查触发条件
                if not self._check_trigger(control, evidence_list):
                    continue
                
                # 检查必要证据
                result = self._check_required_evidence(control, evidence_list)
                
                if result.is_compliant:
                    # 内控已执行
                    continue
                else:
                    # 内控缺失，生成预警
                    alert = self._generate_alert(control, evidence_list, result)
                    alerts.append(alert)
        
        return alerts
    
    def _check_required_evidence(
        self, 
        control: InternalControlProcedure,
        evidence_list: List[BusinessEvidence]
    ) -> CheckResult:
        """
        检查内控所需的证据是否存在
        """
        missing_evidence = []
        partial_evidence = []
        
        for required in control.evidence_required:
            matched = False
            for evidence in evidence_list:
                if self._match_evidence_type(evidence, required):
                    # 检查证据质量
                    if evidence.is_complete:
                        matched = True
                    else:
                        partial_evidence.append(required)
                    break
            
            if not matched:
                missing_evidence.append(required)
        
        if missing_evidence:
            return CheckResult(
                is_compliant=False,
                missing_evidence=missing_evidence,
                partial_evidence=partial_evidence,
            )
        
        if partial_evidence:
            return CheckResult(
                is_compliant=True,
                partial_compliance=True,
                partial_evidence=partial_evidence,
            )
        
        return CheckResult(is_compliant=True)
```

### 3.3 预警生成

```python
class ControlAlert:
    """内控预警"""
    
    # 预警级别
    class AlertLevel:
        CRITICAL = "critical"    # 严重：直接导致重大错报风险
        HIGH = "high"           # 高：可能导致重大错报
        MEDIUM = "medium"       # 中：可能导致一般错报
        LOW = "low"             # 低：可能导致轻微错报
    
    alert_id: str
    control_id: str
    control_name: str
    
    # 预警详情
    alert_level: str
    business_type: str           # 采购/销售/资金
    affected_transaction: str     # 受影响的业务编号
    evidence_involved: List[str] # 涉及的证据
    
    # 问题描述
    problem_type: str            # missing_evidence / incomplete_evidence / delayed_evidence
    description: str
    
    # 风险量化
    inherent_risk: float         # 固有风险 0-1
    control_risk: float          # 控制风险 0-1
    detection_risk: float       # 检查风险 0-1
    overall_risk: float          # 综合风险 0-1
    
    # 审计建议
    suggested_procedure: str      # 建议的审计程序
    priority: int               # 处理优先级 1-10
    created_at: datetime
    
    def to_audit_finding(self) -> AuditFinding:
        """转换为审计发现"""
        return AuditFinding(
            finding_type="internal_control_deficiency",
            severity=self.alert_level,
            title=f"内控缺陷：{self.control_name}",
            description=self.description,
            risk_level=self.overall_risk,
            suggestion=self.suggested_procedure,
            affected_evidence=self.evidence_involved,
        )
```

## 4. 风险量化模型

### 4.1 风险矩阵

```python
# 风险评估矩阵
RISK_MATRIX = {
    #              固有风险
    #         低      中      高
    # 控制   ┌───────┬───────┬───────┐
    # 风险   │  低   │  中   │  高   │
    # 低     │  (1)  │  (2)  │  (3)  │
    #        ├───────┼───────┼───────┤
    # 控制   │  低   │  中   │  高   │
    # 风险   │  (2)  │  (3)  │  高   │
    # 中     │       │       │  (4)  │
    #        ├───────┼───────┼───────┤
    # 控制   │  中   │  高   │  高   │
    # 风险   │  (3)  │  (4)  │  (5)  │
    # 高     │       │       │       │
    #        └───────┴───────┴───────┘
    
    ("low", "low"): {"risk": "low", "score": 1},
    ("low", "medium"): {"risk": "medium", "score": 2},
    ("low", "high"): {"risk": "high", "score": 3},
    ("medium", "low"): {"risk": "medium", "score": 2},
    ("medium", "medium"): {"risk": "high", "score": 3},
    ("medium", "high"): {"risk": "high", "score": 4},
    ("high", "low"): {"risk": "medium", "score": 3},
    ("high", "medium"): {"risk": "high", "score": 4},
    ("high", "high"): {"risk": "critical", "score": 5},
}

def calculate_overall_risk(inherent_risk: str, control_risk: str) -> float:
    """计算综合风险"""
    risk_info = RISK_MATRIX.get((inherent_risk, control_risk), {"risk": "high", "score": 4})
    return risk_info["score"] / 5.0  # 归一化到 0-1
```

### 4.2 风险级别阈值

```python
RISK_THRESHOLDS = {
    "critical": {"min": 0.8, "color": "red", "action": "立即报告管理层"},
    "high": {"min": 0.6, "color": "orange", "action": "扩大审计范围"},
    "medium": {"min": 0.4, "color": "yellow", "action": "增加审计程序"},
    "low": {"min": 0.0, "color": "green", "action": "常规审计程序"},
}
```

## 5. 内控预警与审计活动的集成

### 5.1 预警贯穿整个审计活动

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    审计活动中的内控预警                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   阶段1: 了解被审计单位                                                      │
│   ├─ 行业特征分析 → 加载行业默认内控程序                                      │
│   ├─ 规模评估 → 确定内控详略程度                                            │
│   └─ 生成初始风险评估                                                       │
│                                                                             │
│   阶段2: 内控测试                                                            │
│   ├─ 导入业务证据                                                            │
│   ├─ 逐笔检测内控执行情况                                                   │
│   └─ 实时生成内控预警 ◄─────────── 贯穿提示风险                              │
│                                                                             │
│   阶段3: 实质性程序                                                          │
│   ├─ 根据预警调整审计重点                                                   │
│   ├─ 量化风险级别                                                           │
│   └─ 优先审计高风险领域                                                     │
│                                                                             │
│   阶段4: 审计报告                                                            │
│   ├─ 汇总内控缺陷                                                           │
│   ├─ 量化整体风险水平                                                       │
│   └─ 出具审计意见                                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 预警展示

```python
# 前端预警展示模型
class ControlAlertDisplay:
    """内控预警前端展示"""
    
    # 预警卡片
    alert_card = {
        "level_badge": "🔴 高风险",  # 颜色+图标
        "control_name": "采购申请审批控制",
        "problem": "缺少审批签字记录",
        "affected_amount": "¥50,000",
        "affected_date": "2024-03-15",
        "risk_quantum": "0.75",  # 风险量化值
        "suggested_action": "扩大采购实质性程序",
        "related_evidence": ["采购合同", "入库单"],
    }
    
    # 预警列表排序
    sort_by = ["risk_level", "affected_amount", "date"]
    
    # 预警聚合
    aggregation = {
        "by_risk_level": {"critical": 3, "high": 12, "medium": 25},
        "by_business_type": {"purchase": 20, "sales": 15, "cash": 5},
        "total_risk_score": 156,  # 累计风险分
    }
```

## 6. 技术实现

### 6.1 数据模型

```python
@dataclass
class InternalControl:
    """内控程序"""
    id: str
    industry: str
    company_size: str
    control_type: str
    control_category: str
    description: str
    trigger_conditions: List[str]
    evidence_required: List[str]
    frequency: str
    inherent_risk: str
    control_risk: str

@dataclass
class ControlTestResult:
    """内控测试结果"""
    control_id: str
    transaction_id: str
    
    # 测试结果
    is_executed: bool           # 内控是否执行
    evidence_found: List[str]   # 找到的证据
    evidence_missing: List[str] # 缺失的证据
    execution_quality: str      # 执行质量：full/partial/none
    
    # 风险评估
    inherent_risk: float
    control_risk: float
    detection_risk: float
    overall_risk: float
    
    # 预警
    alert_level: str
    alert_message: str
    suggested_procedure: str
    
    tested_at: datetime
    tester: str = "system"  # system 或人工测试者
```

### 6.2 与现有系统的集成

```python
# 集成到导入流程
class ImportService:
    def process_import(self, files: List[UploadFile]):
        # 1. 解析文件
        evidence_list = self._parse_files(files)
        
        # 2. 构建业务循环
        cycles = self._build_business_cycles(evidence_list)
        
        # 3. 内控检测 ◄── 新增
        control_alerts = self._detect_internal_controls(evidence_list)
        
        # 4. 生成预警
        for alert in control_alerts:
            self._create_risk_alert(alert)
        
        # 5. 业务循环测试
        cycle_results = self._test_business_cycles(cycles)
        
        # 6. 生成审计发现
        findings = self._generate_audit_findings(control_alerts, cycle_results)
        
        return ImportResult(
            evidence_count=len(evidence_list),
            control_alerts=control_alerts,
            findings=findings,
        )
```

## 7. 总结

### 7.1 核心理念

1. **内控是审计的前置程序**：风险导向审计建立在对内控的评估之上
2. **内控文档缺失 ≠ 内控不存在**：从业务证据推断内控执行情况
3. **行业默认内控程序**：建立标准化的内控程序库作为检测基准
4. **实时预警机制**：在审计活动中贯穿提示内控风险
5. **风险量化**：用数学模型量化固有风险、控制风险、检查风险

### 7.2 实现目标

- **标准化**：建立各行业、各规模的默认内控程序库
- **自动化**：从业务证据自动推断内控执行情况
- **实时预警**：在审计过程中实时提示内控风险
- **风险量化**：用数值量化风险级别，支持排序和聚合
- **可追溯**：预警与证据关联，支持审计复核
