"""
审计测试服务 - 业务链条验证与审计发现生成

核心功能：
1. 正向测试：合同 → 入库单 → 发票 → 付款 的业务完整性
2. 逆向测试：发票 → 入库单 → 合同 的业务真实性
3. 审计发现生成：基于审计准则的专业表述
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
import uuid
import re

from .ledger_service import (
    LedgerService,
    LedgerEntry,
    ContractLedger,
    InvoiceLedger,
    InventoryLedger,
    BankStatementLedger,
    BusinessType,
    BusinessDirection,
    BusinessFlowDefinition,
    BUSINESS_FLOWS,
    ledger_service,
)


# ============================================================================
# 审计发现类型枚举
# ============================================================================

class FindingType(str, Enum):
    """审计发现类型"""
    MISSING_CONTRACT = "missing_contract"                    # 缺少合同
    MISSING_INVENTORY = "missing_inventory"                  # 缺少入库单
    MISSING_INVOICE = "missing_invoice"                      # 缺少发票
    MISSING_PAYMENT = "missing_payment"                       # 缺少付款记录
    MISMATCH_AMOUNT = "mismatch_amount"                      # 金额不匹配
    MISMATCH_COUNTERPARTY = "mismatch_counterparty"          # 交易对手不匹配
    TIMING_ANOMALY = "timing_anomaly"                         # 时间异常
    GHOST_INVOICE = "ghost_invoice"                          # 幽灵发票（无业务支撑）
    DUPLICATE_INVOICE = "duplicate_invoice"                  # 重复发票
    CLASSIFICATION_MISMATCH = "classification_mismatch"      # 分类不匹配


class Severity(str, Enum):
    """严重程度"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TestType(str, Enum):
    """测试类型"""
    COMPLETENESS = "completeness"     # 完整性测试
    ACCURACY = "accuracy"             # 准确性测试
    CUTOFF = "cutoff"                 # 截止性测试
    CLASSIFICATION = "classification" # 分类测试


# ============================================================================
# 审计发现模型
# ============================================================================

class AuditFinding(BaseModel):
    """审计发现"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    finding_type: FindingType                    # 发现类型
    severity: Severity                           # 严重程度
    business_type: BusinessType                   # 业务类型
    
    # 定位信息
    related_entries: List[str] = Field(default_factory=list)    # 关联的台账条目ID
    related_files: List[str] = Field(default_factory=list)    # 关联的文件名
    
    # 审计语言表述
    finding_title: str                            # 审计发现标题
    finding_description: str                      # 审计发现描述
    audit_procedure: str                          # 执行的审计程序
    audit_conclusion: str                          # 审计结论
    risk_statement: str                           # 风险表述
    
    # 建议
    recommendation: str                            # 建议措施
    
    # 额外信息
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# 审计报告模型
# ============================================================================

class AuditTestReport(BaseModel):
    """审计测试报告"""
    test_date: str
    period: str                                    # 审计期间
    scope: str                                     # 审计范围
    
    # 测试汇总
    total_transactions: int                       # 总交易数
    tested_transactions: int                      # 已测试交易数
    
    # 正向测试结果
    forward_test: Dict[str, Any]
    
    # 逆向测试结果
    reverse_test: Dict[str, Any]
    
    # 各类测试结果
    completeness_result: Dict[str, Any]
    accuracy_result: Dict[str, Any]
    cutoff_result: Dict[str, Any]
    classification_result: Dict[str, Any]
    
    # 审计发现汇总
    findings: List[AuditFinding]
    
    # 汇总统计
    summary: Dict[str, Any]


# ============================================================================
# 匹配结果模型
# ============================================================================

class MatchResult(BaseModel):
    """匹配结果"""
    matched: bool
    match_score: float = 0.0                       # 0-1
    match_details: Dict[str, Any] = Field(default_factory=dict)
    mismatch_reasons: List[str] = Field(default_factory=list)


# ============================================================================
# 审计测试服务
# ============================================================================

class AuditTestService:
    """审计测试服务"""
    
    # 金额容差（百分比）
    AMOUNT_TOLERANCE_PERCENT = 0.01  # ±1%
    
    # 日期容差（天）
    DATE_TOLERANCE_DAYS = 30
    
    # 交易对手模糊匹配关键词
    COUNTERPARTY_KEYWORDS = [
        "有限公司", "有限责任公司", "股份公司", "集团",
        "Co.,", "Ltd.", "Inc.", "Corp.",
    ]
    
    def __init__(self, ledger_service: LedgerService):
        self.ledger_service = ledger_service
        self.findings: List[AuditFinding] = []
    
    # =========================================================================
    # 核心匹配算法
    # =========================================================================
    
    def match_entries(
        self,
        entry1: LedgerEntry,
        entry2: LedgerEntry,
        match_type: str
    ) -> MatchResult:
        """
        基于金额、日期、交易对手进行匹配
        
        Args:
            entry1: 第一个台账条目
            entry2: 第二个台账条目
            match_type: 匹配类型（如 invoice_to_inventory, inventory_to_contract 等）
        """
        match_score = 0.0
        mismatch_reasons = []
        match_details = {}
        
        # 1. 金额匹配
        if entry1.amount is not None and entry2.amount is not None:
            amount_diff = abs(entry1.amount - entry2.amount)
            amount_sum = max(abs(entry1.amount), abs(entry2.amount), 1)
            amount_ratio = amount_diff / amount_sum
            
            if amount_ratio <= self.AMOUNT_TOLERANCE_PERCENT:
                match_score += 0.4
                match_details["amount_match"] = True
            else:
                mismatch_reasons.append(
                    f"金额不匹配：{entry1.amount} vs {entry2.amount}（差异{amount_ratio*100:.2f}%）"
                )
                match_details["amount_match"] = False
                match_details["amount_diff_percent"] = amount_ratio * 100
        else:
            match_details["amount_match"] = None  # 无法判断
        
        # 2. 日期匹配（根据业务类型有不同的容差）
        if entry1.date and entry2.date:
            try:
                date1 = datetime.strptime(entry1.date, "%Y-%m-%d")
                date2 = datetime.strptime(entry2.date, "%Y-%m-%d")
                days_diff = abs((date1 - date2).days)
                
                # 不同业务类型有不同的日期容差
                if match_type in ["invoice_to_inventory", "inventory_to_contract"]:
                    tolerance = self.DATE_TOLERANCE_DAYS
                else:
                    tolerance = self.DATE_TOLERANCE_DAYS
                
                if days_diff <= tolerance:
                    match_score += 0.3
                    match_details["date_match"] = True
                    match_details["days_diff"] = days_diff
                else:
                    mismatch_reasons.append(
                        f"日期差异过大：{entry1.date} vs {entry2.date}（相差{days_diff}天）"
                    )
                    match_details["date_match"] = False
                    match_details["days_diff"] = days_diff
            except (ValueError, TypeError):
                match_details["date_match"] = None
        else:
            match_details["date_match"] = None
        
        # 3. 交易对手匹配（模糊匹配）
        if entry1.counterparty and entry2.counterparty:
            if self._counterparty_match(entry1.counterparty, entry2.counterparty):
                match_score += 0.3
                match_details["counterparty_match"] = True
            else:
                mismatch_reasons.append(
                    f"交易对手不匹配：{entry1.counterparty} vs {entry2.counterparty}"
                )
                match_details["counterparty_match"] = False
        else:
            match_details["counterparty_match"] = None
        
        # 判断是否匹配（得分 >= 0.7 或金额日期都匹配）
        matched = (
            match_score >= 0.7 or 
            (match_details.get("amount_match") and match_details.get("date_match"))
        )
        
        return MatchResult(
            matched=matched,
            match_score=match_score,
            match_details=match_details,
            mismatch_reasons=mismatch_reasons
        )
    
    def _counterparty_match(self, party1: str, party2: str) -> bool:
        """模糊匹配交易对手"""
        if not party1 or not party2:
            return False
        
        # 清理和标准化
        p1 = self._normalize_company_name(party1)
        p2 = self._normalize_company_name(party2)
        
        # 完全包含
        if p1 in p2 or p2 in p1:
            return True
        
        # 去掉"有限公司"等后缀后比较
        p1_core = re.sub(r'(有限公司|有限责任公司|股份公司|集团|Co.,|Ltd.|Inc.|Corp.)', '', p1)
        p2_core = re.sub(r'(有限公司|有限责任公司|股份公司|集团|Co.,|Ltd.|Inc.|Corp.)', '', p2)
        
        if p1_core and p2_core and (p1_core in p2_core or p2_core in p1_core):
            return True
        
        return False
    
    def _normalize_company_name(self, name: str) -> str:
        """标准化公司名称"""
        if not name:
            return ""
        # 统一转小写，去除空格
        return name.lower().replace(" ", "").replace("　", "")
    
    # =========================================================================
    # 业务链条构建
    # =========================================================================
    
    def build_business_chain(
        self,
        business_type: BusinessType,
        direction: str = "forward"
    ) -> List[Dict[str, Any]]:
        """
        构建业务链条
        
        Args:
            business_type: 业务类型
            direction: forward（正向）或 reverse（逆向）
        
        Returns:
            业务链条列表
        """
        flow_def = BUSINESS_FLOWS.get(business_type)
        if not flow_def:
            return []
        
        chains = []
        
        # 根据方向确定步骤顺序
        if direction == "forward":
            steps = flow_def.steps
        else:
            steps = list(reversed(flow_def.steps))
        
        # 获取所有台账
        ledgers_by_type = {
            "contract": self.ledger_service.contract_ledger,
            "invoice": self.ledger_service.invoice_ledger,
            "inventory": self.ledger_service.inventory_ledger,
            "bank_statement": self.ledger_service.bank_statement_ledger,
        }
        
        # 按步骤匹配构建链条
        for step_idx, step in enumerate(steps):
            step_ledger = ledgers_by_type.get(step.source_type, {})
            
            for entry_id, entry in step_ledger.items():
                chain_entry = {
                    "step_order": step.step_order,
                    "step_name": step.step_name,
                    "source_type": step.source_type,
                    "entry_id": entry_id,
                    "file": entry.source_file,
                    "amount": entry.amount,
                    "date": entry.date,
                    "counterparty": entry.counterparty,
                    "matched": False,
                    "match_details": {},
                }
                
                # 尝试与前一个步骤匹配
                if step_idx > 0:
                    prev_step = steps[step_idx - 1]
                    prev_ledger = ledgers_by_type.get(prev_step.source_type, {})
                    
                    for prev_id, prev_entry in prev_ledger.items():
                        match_result = self.match_entries(
                            entry, prev_entry,
                            f"{step.source_type}_to_{prev_step.source_type}"
                        )
                        if match_result.matched:
                            chain_entry["matched"] = True
                            chain_entry["matched_entry_id"] = prev_id
                            chain_entry["match_details"] = match_result.model_dump()
                            break
                
                chains.append(chain_entry)
        
        return chains
    
    def find_unmatched_entries(
        self,
        business_type: BusinessType,
        source_type: str
    ) -> List[LedgerEntry]:
        """
        查找未匹配的条目（用于识别幽灵发票等）
        """
        ledger = self.ledger_service.get_ledger_by_type(source_type)
        unmatched = []
        
        for entry_id, entry in ledger.items():
            if entry.status == "pending":
                unmatched.append(entry)
        
        return unmatched
    
    # =========================================================================
    # 正向测试
    # =========================================================================
    
    def forward_test(self, business_type: BusinessType) -> Dict[str, Any]:
        """
        正向测试：检查业务链条完整性
        
        正向流程：合同 → 入库单 → 发票 → 付款
        测试目标：所有发票都有原始凭证支撑
        """
        flow_def = BUSINESS_FLOWS.get(business_type)
        if not flow_def:
            return {"error": f"未找到业务类型定义: {business_type}"}
        
        # 获取所有台账
        ledgers_by_type = {
            "contract": self.ledger_service.contract_ledger,
            "invoice": self.ledger_service.invoice_ledger,
            "inventory": self.ledger_service.inventory_ledger,
            "bank_statement": self.ledger_service.bank_statement_ledger,
        }
        
        results = {
            "business_type": business_type.value,
            "flow_description": flow_def.forward_description,
            "total_chains": 0,
            "complete_chains": 0,
            "incomplete_chains": 0,
            "chains_detail": [],
            "missing_steps_summary": {},
        }
        
        # 按步骤顺序构建链条
        steps = flow_def.steps
        
        # 对发票进行分组匹配（以发票为中心）
        invoices = list(self.ledger_service.invoice_ledger.values())
        
        for invoice in invoices:
            chain = {
                "invoice_id": invoice.id,
                "invoice_file": invoice.source_file,
                "invoice_amount": invoice.amount,
                "invoice_date": invoice.date,
                "steps_found": [],
                "complete": False,
            }
            
            results["total_chains"] += 1
            
            # 1. 查找匹配的入库单
            matched_inventory = None
            for inv_id, inv_entry in self.ledger_service.inventory_ledger.items():
                if inv_entry.status == "pending":
                    match_result = self.match_entries(
                        invoice, inv_entry, "invoice_to_inventory"
                    )
                    if match_result.matched:
                        matched_inventory = {
                            "entry_id": inv_id,
                            "file": inv_entry.source_file,
                            "amount": inv_entry.amount,
                            "date": inv_entry.date,
                            "match_score": match_result.match_score,
                        }
                        # 标记为已匹配
                        inv_entry.status = "matched"
                        break
            
            if matched_inventory:
                chain["steps_found"].append({
                    "step_name": "验收入库",
                    "step_order": 2,
                    **matched_inventory
                })
                
                # 2. 查找匹配的合同
                matched_contract = None
                for contract_id, contract in self.ledger_service.contract_ledger.items():
                    if contract.status == "pending":
                        match_result = self.match_entries(
                            inv_entry, contract, "inventory_to_contract"
                        )
                        if match_result.matched:
                            matched_contract = {
                                "entry_id": contract_id,
                                "file": contract.source_file,
                                "amount": contract.amount,
                                "date": contract.date,
                                "match_score": match_result.match_score,
                            }
                            contract.status = "matched"
                            break
                
                if matched_contract:
                    chain["steps_found"].append({
                        "step_name": "合同签订",
                        "step_order": 1,
                        **matched_contract
                    })
                
                # 3. 查找匹配的付款记录
                matched_payment = None
                for payment_id, payment in self.ledger_service.bank_statement_ledger.items():
                    if payment.status == "pending":
                        match_result = self.match_entries(
                            invoice, payment, "invoice_to_payment"
                        )
                        if match_result.matched:
                            matched_payment = {
                                "entry_id": payment_id,
                                "file": payment.source_file,
                                "amount": payment.amount,
                                "date": payment.date,
                                "match_score": match_result.match_score,
                            }
                            payment.status = "matched"
                            break
                
                if matched_payment:
                    chain["steps_found"].append({
                        "step_name": "款项支付",
                        "step_order": 4,
                        **matched_payment
                    })
                
                # 检查链条完整性
                required_steps = [s.step_order for s in steps if s.required]
                found_steps = [s["step_order"] for s in chain["steps_found"]]
                
                if all(rs in found_steps for rs in required_steps):
                    chain["complete"] = True
                    results["complete_chains"] += 1
                else:
                    results["incomplete_chains"] += 1
                    missing = set(required_steps) - set(found_steps)
                    for m in missing:
                        results["missing_steps_summary"][m] = \
                            results["missing_steps_summary"].get(m, 0) + 1
            else:
                results["incomplete_chains"] += 1
                results["missing_steps_summary"][2] = \
                    results["missing_steps_summary"].get(2, 0) + 1
                
                # 生成审计发现
                self._generate_finding(
                    finding_type=FindingType.MISSING_INVENTORY,
                    severity=Severity.HIGH,
                    business_type=business_type,
                    related_entries=[invoice.id],
                    related_files=[invoice.source_file],
                    title="入库单缺失",
                    description=f"发票（{invoice.source_file}）未找到对应的入库单记录",
                    procedure="检查入库单与发票的匹配关系",
                    conclusion="该发票缺乏入库业务支撑",
                    risk="可能存在虚构采购业务或发票与实际业务不符的风险",
                    recommendation="请补充入库单据或核实发票的真实性",
                )
            
            # 添加发票步骤
            chain["steps_found"].append({
                "step_name": "发票开具",
                "step_order": 3,
                "entry_id": invoice.id,
                "file": invoice.source_file,
                "amount": invoice.amount,
                "date": invoice.date,
            })
            
            results["chains_detail"].append(chain)
        
        return results
    
    # =========================================================================
    # 逆向测试
    # =========================================================================
    
    def reverse_test(self, business_type: BusinessType) -> Dict[str, Any]:
        """
        逆向测试：检查业务真实性
        
        逆向流程：发票 → 入库单 → 合同
        测试目标：识别"幽灵发票"（有发票但无真实业务支撑）
        """
        flow_def = BUSINESS_FLOWS.get(business_type)
        if not flow_def:
            return {"error": f"未找到业务类型定义: {business_type}"}
        
        results = {
            "business_type": business_type.value,
            "flow_description": flow_def.reverse_description,
            "total_invoices": 0,
            "verified_invoices": 0,
            "ghost_invoices": 0,
            "ghost_invoice_details": [],
        }
        
        # 获取所有发票
        invoices = list(self.ledger_service.invoice_ledger.values())
        results["total_invoices"] = len(invoices)
        
        for invoice in invoices:
            verification = {
                "invoice_id": invoice.id,
                "invoice_file": invoice.source_file,
                "invoice_amount": invoice.amount,
                "verified": False,
                "supporting_evidence": [],
            }
            
            # 1. 查找入库单支撑
            inventory_found = False
            for inv_id, inv_entry in self.ledger_service.inventory_ledger.items():
                match_result = self.match_entries(
                    invoice, inv_entry, "invoice_to_inventory"
                )
                if match_result.matched:
                    inventory_found = True
                    verification["supporting_evidence"].append({
                        "type": "inventory",
                        "entry_id": inv_id,
                        "file": inv_entry.source_file,
                        "match_score": match_result.match_score,
                    })
                    break
            
            # 2. 查找合同支撑
            contract_found = False
            if inventory_found:
                # 如果找到入库单，尝试匹配合同
                for contract_id, contract in self.ledger_service.contract_ledger.items():
                    match_result = self.match_entries(
                        inv_entry, contract, "inventory_to_contract"
                    )
                    if match_result.matched:
                        contract_found = True
                        verification["supporting_evidence"].append({
                            "type": "contract",
                            "entry_id": contract_id,
                            "file": contract.source_file,
                            "match_score": match_result.match_score,
                        })
                        break
            
            if inventory_found and contract_found:
                verification["verified"] = True
                results["verified_invoices"] += 1
            else:
                results["ghost_invoices"] += 1
                verification["verified"] = False
                verification["missing_evidence"] = []
                
                if not inventory_found:
                    verification["missing_evidence"].append("入库单")
                if not contract_found:
                    verification["missing_evidence"].append("合同")
                
                results["ghost_invoice_details"].append(verification)
                
                # 生成审计发现
                self._generate_finding(
                    finding_type=FindingType.GHOST_INVOICE,
                    severity=Severity.HIGH,
                    business_type=business_type,
                    related_entries=[invoice.id],
                    related_files=[invoice.source_file],
                    title="幽灵发票",
                    description=f"发票（{invoice.source_file}）缺乏真实业务支撑，"
                                f"缺少：{'、'.join(verification['missing_evidence'])}",
                    procedure="执行逆查程序，从发票追查至原始凭证",
                    conclusion="该发票无法证实其真实业务背景",
                    risk="可能存在虚开发票、虚构业务的风险",
                    recommendation="请进一步核实该发票的真实性，获取完整的业务链条证据",
                )
        
        return results
    
    # =========================================================================
    # 各类测试
    # =========================================================================
    
    def completeness_test(self, business_type: BusinessType) -> Dict[str, Any]:
        """
        完整性测试：检查所有发票是否有原始凭证支撑
        """
        forward_result = self.forward_test(business_type)
        
        total = forward_result.get("total_chains", 0)
        complete = forward_result.get("complete_chains", 0)
        incomplete = forward_result.get("incomplete_chains", 0)
        
        completeness_rate = complete / total if total > 0 else 0
        
        return {
            "test_type": TestType.COMPLETENESS.value,
            "business_type": business_type.value,
            "total_invoices": total,
            "with_full_support": complete,
            "without_full_support": incomplete,
            "completeness_rate": completeness_rate,
            "pass": completeness_rate >= 0.95,
            "details": forward_result.get("chains_detail", []),
        }
    
    def accuracy_test(self, business_type: BusinessType) -> Dict[str, Any]:
        """
        准确性测试：检查发票金额与付款金额是否一致
        """
        results = {
            "test_type": TestType.ACCURACY.value,
            "business_type": business_type.value,
            "total_compared": 0,
            "matched": 0,
            "mismatched": 0,
            "mismatches": [],
        }
        
        # 比较发票与付款记录
        for invoice_id, invoice in self.ledger_service.invoice_ledger.items():
            if invoice.amount is None:
                continue
            
            for payment_id, payment in self.ledger_service.bank_statement_ledger.items():
                if payment.amount is None:
                    continue
                
                results["total_compared"] += 1
                
                amount_diff = abs(invoice.amount - payment.amount)
                amount_sum = max(abs(invoice.amount), abs(payment.amount), 1)
                amount_ratio = amount_diff / amount_sum
                
                if amount_ratio <= self.AMOUNT_TOLERANCE_PERCENT:
                    results["matched"] += 1
                else:
                    results["mismatched"] += 1
                    results["mismatches"].append({
                        "invoice_id": invoice_id,
                        "invoice_file": invoice.source_file,
                        "invoice_amount": invoice.amount,
                        "payment_id": payment_id,
                        "payment_file": payment.source_file,
                        "payment_amount": payment.amount,
                        "difference": amount_diff,
                        "difference_percent": amount_ratio * 100,
                    })
                    
                    # 生成审计发现
                    self._generate_finding(
                        finding_type=FindingType.MISMATCH_AMOUNT,
                        severity=Severity.MEDIUM,
                        business_type=business_type,
                        related_entries=[invoice_id, payment_id],
                        related_files=[invoice.source_file, payment.source_file],
                        title="发票金额与付款金额不一致",
                        description=f"发票金额（{invoice.amount}）与付款金额（{payment.amount}）"
                                    f"存在差异，差异率{amount_ratio*100:.2f}%",
                        procedure="核对发票与银行流水的金额一致性",
                        conclusion="发票与付款金额不匹配",
                        risk="可能存在发票金额错误或付款不完整风险",
                        recommendation="核实发票和付款记录，确保金额一致",
                    )
        
        accuracy_rate = results["matched"] / results["total_compared"] if results["total_compared"] > 0 else 0
        results["accuracy_rate"] = accuracy_rate
        results["pass"] = accuracy_rate >= 0.95
        
        return results
    
    def cutoff_test(
        self,
        business_type: BusinessType,
        period_start: str,
        period_end: str
    ) -> Dict[str, Any]:
        """
        截止性测试：检查分录是否在正确期间
        
        Args:
            business_type: 业务类型
            period_start: 期间开始日期（YYYY-MM-DD）
            period_end: 期间结束日期（YYYY-MM-DD）
        """
        results = {
            "test_type": TestType.CUTOFF.value,
            "business_type": business_type.value,
            "period": f"{period_start} 至 {period_end}",
            "total_entries": 0,
            "in_period": 0,
            "out_of_period": 0,
            "out_of_period_details": [],
        }
        
        try:
            start_date = datetime.strptime(period_start, "%Y-%m-%d")
            end_date = datetime.strptime(period_end, "%Y-%m-%d")
        except ValueError:
            return {"error": "日期格式错误，请使用 YYYY-MM-DD 格式"}
        
        # 检查所有台账
        ledgers = [
            self.ledger_service.contract_ledger,
            self.ledger_service.invoice_ledger,
            self.ledger_service.inventory_ledger,
            self.ledger_service.bank_statement_ledger,
        ]
        
        for ledger in ledgers:
            for entry_id, entry in ledger.items():
                if not entry.date:
                    continue
                
                results["total_entries"] += 1
                
                try:
                    entry_date = datetime.strptime(entry.date, "%Y-%m-%d")
                    
                    if start_date <= entry_date <= end_date:
                        results["in_period"] += 1
                    else:
                        results["out_of_period"] += 1
                        results["out_of_period_details"].append({
                            "entry_id": entry_id,
                            "source_file": entry.source_file,
                            "source_type": entry.source_type,
                            "date": entry.date,
                            "amount": entry.amount,
                        })
                except ValueError:
                    pass
        
        cutoff_rate = results["in_period"] / results["total_entries"] if results["total_entries"] > 0 else 0
        results["cutoff_rate"] = cutoff_rate
        results["pass"] = cutoff_rate >= 0.98
        
        return results
    
    def classification_test(
        self,
        business_type: BusinessType,
        voucher_type_mapping: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """
        分类测试：检查凭证字与业务类型是否匹配
        
        Args:
            business_type: 业务类型
            voucher_type_mapping: 凭证字与业务类型的映射，如 {"采购": "purchase", "销售": "sales"}
        """
        if voucher_type_mapping is None:
            voucher_type_mapping = {
                "采购": BusinessType.PURCHASE,
                "销售": BusinessType.SALES,
                "费用": BusinessType.EXPENSE,
            }
        
        results = {
            "test_type": TestType.CLASSIFICATION.value,
            "business_type": business_type.value,
            "total_entries": 0,
            "correctly_classified": 0,
            "misclassified": 0,
            "misclassification_details": [],
        }
        
        # 检查发票的业务类型分类
        for invoice_id, invoice in self.ledger_service.invoice_ledger.items():
            if not invoice.business_type:
                continue
            
            results["total_entries"] += 1
            
            # 检查分类是否合理（这里简化处理）
            # 实际应该检查凭证字或其他分类字段
            expected_type = self._infer_business_type(invoice)
            
            if expected_type == invoice.business_type:
                results["correctly_classified"] += 1
            else:
                results["misclassified"] += 1
                results["misclassification_details"].append({
                    "invoice_id": invoice_id,
                    "invoice_file": invoice.source_file,
                    "classified_as": invoice.business_type.value,
                    "expected_type": expected_type.value if expected_type else None,
                })
        
        classification_rate = (
            results["correctly_classified"] / results["total_entries"] 
            if results["total_entries"] > 0 else 0
        )
        results["classification_rate"] = classification_rate
        results["pass"] = classification_rate >= 0.9
        
        return results
    
    def _infer_business_type(self, invoice: InvoiceLedger) -> Optional[BusinessType]:
        """根据发票信息推断业务类型"""
        # 简化实现：根据购买方和销售方推断
        if invoice.buyer_name and any(kw in invoice.buyer_name for kw in ["采购", "购入"]):
            return BusinessType.PURCHASE
        if invoice.seller_name and any(kw in invoice.seller_name for kw in ["采购", "购入"]):
            return BusinessType.PURCHASE
        return BusinessType.OTHER
    
    # =========================================================================
    # 审计发现生成
    # =========================================================================
    
    def _generate_finding(
        self,
        finding_type: FindingType,
        severity: Severity,
        business_type: BusinessType,
        related_entries: List[str],
        related_files: List[str],
        title: str,
        description: str,
        procedure: str,
        conclusion: str,
        risk: str,
        recommendation: str,
    ) -> AuditFinding:
        """生成审计发现"""
        finding = AuditFinding(
            finding_type=finding_type,
            severity=severity,
            business_type=business_type,
            related_entries=related_entries,
            related_files=related_files,
            finding_title=title,
            finding_description=description,
            audit_procedure=procedure,
            audit_conclusion=conclusion,
            risk_statement=risk,
            recommendation=recommendation,
        )
        
        self.findings.append(finding)
        return finding
    
    def get_findings(
        self,
        severity: Severity = None,
        finding_type: FindingType = None,
        business_type: BusinessType = None,
    ) -> List[AuditFinding]:
        """获取审计发现列表"""
        results = self.findings
        
        if severity:
            results = [f for f in results if f.severity == severity]
        if finding_type:
            results = [f for f in results if f.finding_type == finding_type]
        if business_type:
            results = [f for f in results if f.business_type == business_type]
        
        return results
    
    # =========================================================================
    # 审计报告生成
    # =========================================================================
    
    def generate_report(
        self,
        period: str,
        scope: str,
        period_start: str = None,
        period_end: str = None,
    ) -> AuditTestReport:
        """
        生成审计测试报告
        
        Args:
            period: 审计期间
            scope: 审计范围
            period_start: 期间开始日期
            period_end: 期间结束日期
        """
        # 执行所有测试
        forward_test_purchase = self.forward_test(BusinessType.PURCHASE)
        forward_test_sales = self.forward_test(BusinessType.SALES)
        reverse_test_purchase = self.reverse_test(BusinessType.PURCHASE)
        reverse_test_sales = self.reverse_test(BusinessType.SALES)
        
        completeness_purchase = self.completeness_test(BusinessType.PURCHASE)
        completeness_sales = self.completeness_test(BusinessType.SALES)
        accuracy_purchase = self.accuracy_test(BusinessType.PURCHASE)
        accuracy_sales = self.accuracy_test(BusinessType.SALES)
        
        cutoff = None
        if period_start and period_end:
            cutoff = self.cutoff_test(BusinessType.PURCHASE, period_start, period_end)
        
        # 汇总统计
        total_transactions = (
            forward_test_purchase.get("total_chains", 0) +
            forward_test_sales.get("total_chains", 0)
        )
        tested_transactions = (
            forward_test_purchase.get("complete_chains", 0) +
            forward_test_sales.get("complete_chains", 0)
        )
        
        report = AuditTestReport(
            test_date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            period=period,
            scope=scope,
            total_transactions=total_transactions,
            tested_transactions=tested_transactions,
            forward_test={
                "purchase": forward_test_purchase,
                "sales": forward_test_sales,
                "summary": {
                    "total_chains": total_transactions,
                    "complete_chains": tested_transactions,
                    "completeness_rate": tested_transactions / total_transactions if total_transactions > 0 else 0,
                },
            },
            reverse_test={
                "purchase": reverse_test_purchase,
                "sales": reverse_test_sales,
                "summary": {
                    "total_invoices": (
                        reverse_test_purchase.get("total_invoices", 0) +
                        reverse_test_sales.get("total_invoices", 0)
                    ),
                    "verified": (
                        reverse_test_purchase.get("verified_invoices", 0) +
                        reverse_test_sales.get("verified_invoices", 0)
                    ),
                    "ghost_invoices": (
                        reverse_test_purchase.get("ghost_invoices", 0) +
                        reverse_test_sales.get("ghost_invoices", 0)
                    ),
                },
            },
            completeness_result={
                "purchase": completeness_purchase,
                "sales": completeness_sales,
                "summary": {
                    "total": (
                        completeness_purchase.get("total_invoices", 0) +
                        completeness_sales.get("total_invoices", 0)
                    ),
                    "with_support": (
                        completeness_purchase.get("with_full_support", 0) +
                        completeness_sales.get("with_full_support", 0)
                    ),
                    "rate": (
                        (completeness_purchase.get("completeness_rate", 0) +
                         completeness_sales.get("completeness_rate", 0)) / 2
                    ),
                },
            },
            accuracy_result={
                "purchase": accuracy_purchase,
                "sales": accuracy_sales,
                "summary": {
                    "total_compared": (
                        accuracy_purchase.get("total_compared", 0) +
                        accuracy_sales.get("total_compared", 0)
                    ),
                    "matched": (
                        accuracy_purchase.get("matched", 0) +
                        accuracy_sales.get("matched", 0)
                    ),
                    "rate": (
                        (accuracy_purchase.get("accuracy_rate", 0) +
                         accuracy_sales.get("accuracy_rate", 0)) / 2
                    ),
                },
            },
            cutoff_result=cutoff or {"note": "未执行截止性测试"},
            classification_result={"note": "待实现"},
            findings=self.findings,
            summary={
                "total_findings": len(self.findings),
                "high_severity": len([f for f in self.findings if f.severity == Severity.HIGH]),
                "medium_severity": len([f for f in self.findings if f.severity == Severity.MEDIUM]),
                "low_severity": len([f for f in self.findings if f.severity == Severity.LOW]),
                "by_type": {
                    ft.value: len([f for f in self.findings if f.finding_type == ft])
                    for ft in FindingType
                },
            },
        )
        
        return report
    
    def clear_findings(self):
        """清除所有审计发现"""
        self.findings = []
    
    def reset_ledger_status(self):
        """重置台账条目的匹配状态"""
        ledgers = [
            self.ledger_service.contract_ledger,
            self.ledger_service.invoice_ledger,
            self.ledger_service.inventory_ledger,
            self.ledger_service.bank_statement_ledger,
        ]
        
        for ledger in ledgers:
            for entry_id, entry in ledger.items():
                entry.status = "pending"


# ============================================================================
# 单例实例
# ============================================================================

audit_test_service = AuditTestService(ledger_service)
