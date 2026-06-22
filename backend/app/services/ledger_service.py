"""
台账服务 - 业务流转与关联映射

核心设计理念：
1. 不同原始凭证解析后形成各自的台账
2. 台账之间基于业务逻辑关联
3. 支持正向（完整性测试）和逆向（存在性测试）测试
4. 业务中断点即为审计风险点
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


# ============================================================================
# 业务类型枚举
# ============================================================================

class BusinessType(str, Enum):
    """业务类型"""
    PURCHASE = "purchase"           # 采购业务
    SALES = "sales"                 # 销售业务
    EXPENSE = "expense"             # 费用业务
    PAYROLL = "payroll"             # 工资业务
    FIXED_ASSET = "fixed_asset"     # 固定资产
    OTHER = "other"                 # 其他业务


class BusinessDirection(str, Enum):
    """业务方向"""
    FORWARD = "forward"   # 正向：合同→入库→发票→付款
    REVERSE = "reverse"    # 逆向：发票→入库单→合同


# ============================================================================
# 台账基础模型
# ============================================================================

class LedgerEntry(BaseModel):
    """台账条目基类"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_file: str                                    # 来源文件名
    source_type: str                                    # 来源类型：invoice/bank_statement/contract/inventory
    business_type: Optional[BusinessType] = None         # 业务类型
    amount: Optional[float] = None                       # 金额
    date: Optional[str] = None                           # 日期
    counterparty: Optional[str] = None                   # 交易对手
    status: str = "pending"                             # 状态：pending/matched/unmatched/error
    confidence: float = 1.0                             # 解析置信度
    metadata: Dict[str, Any] = Field(default_factory=dict)  # 扩展字段
    created_at: datetime = Field(default_factory=datetime.now)


class ContractLedger(LedgerEntry):
    """合同台账"""
    source_type: str = "contract"
    contract_number: Optional[str] = None               # 合同编号
    party_a: Optional[str] = None                        # 甲方
    party_b: Optional[str] = None                        # 乙方
    sign_date: Optional[str] = None                      # 签订日期
    contract_amount: Optional[float] = None              # 合同金额
    payment_terms: Optional[str] = None                 # 付款条款


class InvoiceLedger(LedgerEntry):
    """发票台账"""
    source_type: str = "invoice"
    invoice_number: Optional[str] = None                 # 发票号码
    invoice_type: Optional[str] = None                   # 发票类型：增值税专用/普通
    buyer_name: Optional[str] = None                     # 购买方
    seller_name: Optional[str] = None                    # 销售方
    tax_amount: Optional[float] = None                   # 税额
    tax_rate: Optional[float] = None                    # 税率
    items: List[Dict[str, Any]] = Field(default_factory=list)  # 商品明细


class InventoryLedger(LedgerEntry):
    """出入库台账"""
    source_type: str = "inventory"
    document_type: Optional[str] = None                  # 单据类型：入库单/出库单
    document_number: Optional[str] = None                # 单据编号
    warehouse: Optional[str] = None                      # 仓库
    supplier: Optional[str] = None                       # 供应商/客户
    items: List[Dict[str, Any]] = Field(default_factory=list)  # 商品明细


class BankStatementLedger(LedgerEntry):
    """银行流水台账"""
    source_type: str = "bank_statement"
    transaction_number: Optional[str] = None             # 交易流水号
    counterparty_account: Optional[str] = None           # 对方账号
    counterparty_bank: Optional[str] = None             # 对方银行
    transaction_type: Optional[str] = None               # 交易类型：收入/支出
    balance: Optional[float] = None                      # 余额


class PayrollLedger(LedgerEntry):
    """工资台账"""
    source_type: str = "payroll"
    period: Optional[str] = None                         # 工资期间
    total_amount: Optional[float] = None                # 工资总额
    employee_count: Optional[int] = None                # 员工人数
    social_security: Optional[float] = None              # 社保
    housing_fund: Optional[float] = None                  # 公积金


# ============================================================================
# 业务流转定义
# ============================================================================

class BusinessFlowStep(BaseModel):
    """业务流转步骤"""
    step_name: str                                       # 步骤名称
    step_order: int                                      # 步骤序号
    source_type: str                                     # 关联的台账类型
    required: bool = True                               # 是否必须
    key_field_mapping: Dict[str, str] = Field(default_factory=dict)  # 关联字段映射
    time_tolerance_days: int = 30                        # 时间容差（天）
    amount_tolerance_percent: float = 0.01               # 金额容差（百分比）


class BusinessFlowDefinition(BaseModel):
    """业务流转定义"""
    business_type: BusinessType
    flow_name: str                                       # 流转名称
    forward_description: str                             # 正向描述
    reverse_description: str                             # 逆向描述
    steps: List[BusinessFlowStep]                        # 流转步骤
    linking_fields: List[str] = Field(default_factory=list)  # 关联字段（用于匹配）


# 预定义业务流转
BUSINESS_FLOWS: Dict[BusinessType, BusinessFlowDefinition] = {
    BusinessType.PURCHASE: BusinessFlowDefinition(
        business_type=BusinessType.PURCHASE,
        flow_name="采购业务流",
        forward_description="合同 → 入库单 → 发票 → 付款",
        reverse_description="发票 → 入库单 → 合同",
        steps=[
            BusinessFlowStep(
                step_name="合同签订",
                step_order=1,
                source_type="contract",
                required=True,
                linking_fields=["contract_number", "party_b", "contract_amount"],
            ),
            BusinessFlowStep(
                step_name="验收入库",
                step_order=2,
                source_type="inventory",
                required=True,
                linking_fields=["supplier", "contract_number"],
            ),
            BusinessFlowStep(
                step_name="发票开具",
                step_order=3,
                source_type="invoice",
                required=True,
                linking_fields=["seller_name", "buyer_name"],
            ),
            BusinessFlowStep(
                step_name="款项支付",
                step_order=4,
                source_type="bank_statement",
                required=False,
                linking_fields=["counterparty", "amount"],
            ),
        ],
    ),
    BusinessType.SALES: BusinessFlowDefinition(
        business_type=BusinessType.SALES,
        flow_name="销售业务流",
        forward_description="合同 → 出库单 → 发票 → 收款",
        reverse_description="发票 → 出库单 → 合同",
        steps=[
            BusinessFlowStep(
                step_name="合同签订",
                step_order=1,
                source_type="contract",
                required=True,
                linking_fields=["contract_number", "party_a"],
            ),
            BusinessFlowStep(
                step_name="出库发货",
                step_order=2,
                source_type="inventory",
                required=True,
                linking_fields=["supplier", "document_type"],
            ),
            BusinessFlowStep(
                step_name="发票开具",
                step_order=3,
                source_type="invoice",
                required=True,
                linking_fields=["seller_name", "buyer_name"],
            ),
            BusinessFlowStep(
                step_name="款项收回",
                step_order=4,
                source_type="bank_statement",
                required=False,
                linking_fields=["counterparty", "amount"],
            ),
        ],
    ),
    BusinessType.EXPENSE: BusinessFlowDefinition(
        business_type=BusinessType.EXPENSE,
        flow_name="费用报销流",
        forward_description="发票/收据 → 付款",
        reverse_description="付款 → 发票",
        steps=[
            BusinessFlowStep(
                step_name="费用发生",
                step_order=1,
                source_type="invoice",
                required=True,
                linking_fields=["buyer_name", "amount"],
            ),
            BusinessFlowStep(
                step_name="款项支付",
                step_order=2,
                source_type="bank_statement",
                required=False,
                linking_fields=["counterparty", "amount"],
            ),
        ],
    ),
}


# ============================================================================
# 业务关联记录
# ============================================================================

class BusinessLink(BaseModel):
    """业务关联记录"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    business_type: BusinessType
    direction: BusinessDirection
    
    # 关联的台账条目ID列表（按业务顺序）
    linked_entries: List[str] = []
    
    # 关联详情
    link_details: List[Dict[str, Any]] = Field(default_factory=list)
    
    # 完整性评估
    completeness_score: float = 0.0                      # 0-1
    missing_steps: List[int] = Field(default_factory=list)  # 缺失的步骤序号
    
    # 风险评估
    risk_level: str = "low"                             # low/medium/high
    risk_reasons: List[str] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=datetime.now)


# ============================================================================
# 台账服务
# ============================================================================

class LedgerService:
    """台账服务 - 管理各类台账和业务流转"""
    
    def __init__(self):
        # 内存存储（后续可接入数据库）
        self.contract_ledger: Dict[str, ContractLedger] = {}
        self.invoice_ledger: Dict[str, InvoiceLedger] = {}
        self.inventory_ledger: Dict[str, InventoryLedger] = {}
        self.bank_statement_ledger: Dict[str, BankStatementLedger] = {}
        self.payroll_ledger: Dict[str, PayrollLedger] = {}
        # 按功能模块分组的台账（税务/银行/往来/采购/销售等）
        self.module_ledgers: Dict[str, Dict[str, LedgerEntry]] = {}
        
        # 业务关联记录
        self.business_links: List[BusinessLink] = []
    
    def add_contract(self, data: Dict[str, Any], source_file: str) -> ContractLedger:
        """添加合同台账"""
        entry = ContractLedger(
            source_file=source_file,
            source_type="contract",
            contract_number=data.get("contract_number"),
            party_a=data.get("party_a"),
            party_b=data.get("party_b"),
            sign_date=data.get("sign_date"),
            contract_amount=data.get("amount") or data.get("contract_amount"),
            counterparty=data.get("party_b"),
            amount=data.get("amount") or data.get("contract_amount"),
            date=data.get("sign_date"),
            confidence=data.get("confidence", 1.0),
            metadata=data,
        )
        self.contract_ledger[entry.id] = entry
        return entry
    
    def add_invoice(self, data: Dict[str, Any], source_file: str) -> InvoiceLedger:
        """添加发票台账"""
        entry = InvoiceLedger(
            source_file=source_file,
            source_type="invoice",
            invoice_number=data.get("invoice_number"),
            invoice_type=data.get("invoice_type"),
            buyer_name=data.get("buyer_name"),
            seller_name=data.get("seller_name"),
            tax_amount=data.get("tax_amount"),
            tax_rate=data.get("tax_rate"),
            items=data.get("items", []),
            counterparty=data.get("seller_name"),
            amount=data.get("total_amount"),
            date=data.get("invoice_date"),
            confidence=data.get("confidence", 1.0),
            metadata=data,
        )
        self.invoice_ledger[entry.id] = entry
        return entry
    
    def add_inventory(self, data: Dict[str, Any], source_file: str) -> InventoryLedger:
        """添加出入库台账"""
        entry = InventoryLedger(
            source_file=source_file,
            source_type="inventory",
            document_type=data.get("document_type"),
            document_number=data.get("receipt_number") or data.get("document_number"),
            warehouse=data.get("warehouse"),
            supplier=data.get("supplier"),
            items=data.get("items", []),
            counterparty=data.get("supplier"),
            amount=data.get("total_amount"),
            date=data.get("receipt_date") or data.get("inventory_date"),
            confidence=data.get("confidence", 1.0),
            metadata=data,
        )
        self.inventory_ledger[entry.id] = entry
        return entry
    
    def add_bank_statement(self, data: Dict[str, Any], source_file: str) -> BankStatementLedger:
        """添加银行流水台账"""
        entry = BankStatementLedger(
            source_file=source_file,
            source_type="bank_statement",
            transaction_number=data.get("transaction_number"),
            counterparty=data.get("counterparty"),
            counterparty_account=data.get("counterparty_account"),
            counterparty_bank=data.get("counterparty_bank"),
            transaction_type=data.get("transaction_type"),
            amount=data.get("amount"),
            date=data.get("transaction_date"),
            balance=data.get("balance"),
            confidence=data.get("confidence", 1.0),
            metadata=data,
        )
        self.bank_statement_ledger[entry.id] = entry
        return entry
    
    def get_ledger_by_type(self, source_type: str) -> Dict[str, LedgerEntry]:
        """根据类型获取台账"""
        ledger_map = {
            "contract": self.contract_ledger,
            "invoice": self.invoice_ledger,
            "inventory": self.inventory_ledger,
            "bank_statement": self.bank_statement_ledger,
            "payroll": self.payroll_ledger,
        }
        return ledger_map.get(source_type, {})
    
    def build_business_link(
        self,
        business_type: BusinessType,
        direction: BusinessDirection = BusinessDirection.FORWARD
    ) -> BusinessLink:
        """
        构建业务关联
        基于业务流转定义，尝试将各台账中的条目关联起来
        """
        flow_def = BUSINESS_FLOWS.get(business_type)
        if not flow_def:
            raise ValueError(f"未找到业务类型定义: {business_type}")
        
        linked_entries = []
        link_details = []
        missing_steps = []
        risk_reasons = []
        
        # 获取关联的台账
        ledgers_by_type = {
            "contract": self.contract_ledger,
            "invoice": self.invoice_ledger,
            "inventory": self.inventory_ledger,
            "bank_statement": self.bank_statement_ledger,
        }
        
        # 按步骤顺序关联
        for step in flow_def.steps:
            step_ledger = ledgers_by_type.get(step.source_type, {})
            
            if not step_ledger:
                if step.required:
                    missing_steps.append(step.step_order)
                    risk_reasons.append(f"缺少{step.step_name}证据")
                continue
            
            # 查找匹配的条目（简化版：取第一个，后续可优化匹配逻辑）
            matched_entry = None
            for entry_id, entry in step_ledger.items():
                if entry.status != "matched":
                    matched_entry = entry
                    entry.status = "matched"
                    break
            
            if matched_entry:
                linked_entries.append(matched_entry.id)
                link_details.append({
                    "step_order": step.step_order,
                    "step_name": step.step_name,
                    "entry_id": matched_entry.id,
                    "file": matched_entry.source_file,
                    "amount": matched_entry.amount,
                    "date": matched_entry.date,
                })
            else:
                if step.required:
                    missing_steps.append(step.step_order)
                    risk_reasons.append(f"缺少{step.step_name}证据")
        
        # 计算完整性得分
        total_required = sum(1 for s in flow_def.steps if s.required)
        matched_required = total_required - len(missing_steps)
        completeness_score = matched_required / total_required if total_required > 0 else 0
        
        # 风险评估
        risk_level = "low"
        if completeness_score < 0.5:
            risk_level = "high"
        elif completeness_score < 1.0:
            risk_level = "medium"
        
        link = BusinessLink(
            business_type=business_type,
            direction=direction,
            linked_entries=linked_entries,
            link_details=link_details,
            completeness_score=completeness_score,
            missing_steps=missing_steps,
            risk_level=risk_level,
            risk_reasons=risk_reasons,
        )
        
        self.business_links.append(link)
        return link
    
    def analyze_all_business_flows(self) -> Dict[str, Any]:
        """分析所有业务流转"""
        results = {
            "total_links": len(self.business_links),
            "by_business_type": {},
            "risk_summary": {
                "high": 0,
                "medium": 0,
                "low": 0,
            },
            "missing_steps_summary": {},
        }
        
        for link in self.business_links:
            bt = link.business_type.value
            if bt not in results["by_business_type"]:
                results["by_business_type"][bt] = []
            results["by_business_type"][bt].append(link.model_dump())
            
            results["risk_summary"][link.risk_level] += 1
            
            for step in link.missing_steps:
                results["missing_steps_summary"][step] = results["missing_steps_summary"].get(step, 0) + 1
        
        return results
    
    def get_audit_test_result(self, business_type: BusinessType) -> Dict[str, Any]:
        """获取审计测试结果"""
        flow_def = BUSINESS_FLOWS.get(business_type)
        links = [l for l in self.business_links if l.business_type == business_type]
        
        # 正向测试：检查业务完整性
        forward_links = [l for l in links if l.direction == BusinessDirection.FORWARD]
        forward_complete = sum(1 for l in forward_links if l.completeness_score >= 1.0)
        
        # 逆向测试：检查业务真实性
        reverse_links = [l for l in links if l.direction == BusinessDirection.REVERSE]
        reverse_complete = sum(1 for l in reverse_links if l.completeness_score >= 1.0)
        
        # 风险汇总
        high_risk = sum(1 for l in links if l.risk_level == "high")
        medium_risk = sum(1 for l in links if l.risk_level == "medium")
        
        return {
            "business_type": business_type.value,
            "flow_description": flow_def.forward_description if flow_def else "",
            "total_transactions": len(links),
            "forward_test": {
                "total": len(forward_links),
                "complete": forward_complete,
                "incomplete": len(forward_links) - forward_complete,
                "completeness_rate": forward_complete / len(forward_links) if forward_links else 0,
            },
            "reverse_test": {
                "total": len(reverse_links),
                "complete": reverse_complete,
                "incomplete": len(reverse_links) - reverse_complete,
            },
            "risk_summary": {
                "high_risk_count": high_risk,
                "medium_risk_count": medium_risk,
            },
            "findings": [
                {
                    "risk_level": link.risk_level,
                    "missing_steps": link.missing_steps,
                    "risk_reasons": link.risk_reasons,
                    "linked_files": [d["file"] for d in link.link_details],
                }
                for link in links
                if link.risk_level != "low"
            ],
        }


# ============================================================================
# 单例实例
# ============================================================================

ledger_service = LedgerService()
