# -*- coding: utf-8 -*-
"""
模块功能：合同深度分析器（ContractDeepAnalyzer）- 超越字段提取，实现语义理解与风险识别
业务场景：审计师在解析合同时，需要识别模糊条款、矛盾表述、缺失要素、异常约定等需要专业判断的内容
政策依据：
    - 企业会计准则第 14 号——收入（五步法模型）
    - 企业会计准则第 13 号——或有事项（违约责任预提）
    - 企业会计准则第 22 号——金融工具确认和计量（预期信用损失）
    - 合同法及合同管理规范
输入数据：合同原始文本、结构化解析结果
输出结果：深度分析报告，包含风险等级、矛盾检测、缺失预警、非标条款标记、会计处理建议
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建，实现合同深度分析能力
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional
from datetime import datetime


class RiskLevel(Enum):
    """风险等级"""
    CRITICAL = "critical"      # 重大风险：可能导致重大错报或合规问题
    HIGH = "high"              # 高风险：需要审计师重点关注
    MEDIUM = "medium"          # 中等风险：建议复核确认
    LOW = "low"                # 低风险：提示性信息
    INFO = "info"              # 信息性：仅提供参考


class RiskCategory(Enum):
    """风险类别"""
    CONTRADICTION = "contradiction"        # 条款矛盾
    MISSING_ELEMENT = "missing_element"    # 关键要素缺失
    NON_STANDARD = "non_standard"          # 非标条款
    AMBIGUITY = "ambiguity"                # 表述模糊
    COMPLIANCE = "compliance"              # 合规风险
    ACCOUNTING_IMPLICATION = "accounting"  # 会计影响
    FINANCIAL_RISK = "financial"           # 财务风险


@dataclass
class ContractRiskItem:
    """合同风险项"""
    risk_level: RiskLevel
    risk_category: RiskCategory
    title: str
    description: str
    clause_reference: str = ""
    location: str = ""
    accounting_impact: str = ""
    recommendation: str = ""
    confidence: float = 0.0


@dataclass
class ClauseContradiction:
    """条款矛盾检测结果"""
    clause_a: str
    clause_b: str
    contradiction_type: str
    description: str
    risk_level: RiskLevel


@dataclass
class MissingElement:
    """关键要素缺失预警"""
    element_name: str
    element_category: str
    importance: str
    description: str
    suggested_action: str


@dataclass
class NonStandardClause:
    """非标条款标记"""
    clause_text: str
    clause_type: str
    deviation_from_standard: str
    risk_description: str
    risk_level: RiskLevel
    accounting_treatment: str


@dataclass
class AmbiguousExpression:
    """模糊表述识别"""
    expression: str
    ambiguity_type: str
    possible_interpretations: list[str] = field(default_factory=list)
    recommended_clarification: str = ""


@dataclass
class ContractDeepAnalysisResult:
    """合同深度分析结果"""
    # 整体评估
    overall_risk_level: RiskLevel
    risk_score: float
    analysis_summary: str
    
    # 各类分析结果
    contradictions: list[ClauseContradiction] = field(default_factory=list)
    missing_elements: list[MissingElement] = field(default_factory=list)
    non_standard_clauses: list[NonStandardClause] = field(default_factory=list)
    ambiguous_expressions: list[AmbiguousExpression] = field(default_factory=list)
    all_risk_items: list[ContractRiskItem] = field(default_factory=list)
    
    # 会计处理建议
    accounting_notes: str = ""
    revenue_recognition_considerations: str = ""
    provision_requirements: str = ""
    
    # 统计信息
    total_clauses_analyzed: int = 0
    risk_clauses_found: int = 0
    
    # 时间戳
    analysis_time: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式"""
        return {
            "overall_risk_level": self.overall_risk_level.value,
            "risk_score": self.risk_score,
            "analysis_summary": self.analysis_summary,
            "contradictions": [
                {
                    "clause_a": c.clause_a,
                    "clause_b": c.clause_b,
                    "contradiction_type": c.contradiction_type,
                    "description": c.description,
                    "risk_level": c.risk_level.value,
                }
                for c in self.contradictions
            ],
            "missing_elements": [
                {
                    "element_name": m.element_name,
                    "element_category": m.element_category,
                    "importance": m.importance,
                    "description": m.description,
                    "suggested_action": m.suggested_action,
                }
                for m in self.missing_elements
            ],
            "non_standard_clauses": [
                {
                    "clause_text": n.clause_text,
                    "clause_type": n.clause_type,
                    "deviation_from_standard": n.deviation_from_standard,
                    "risk_description": n.risk_description,
                    "risk_level": n.risk_level.value,
                    "accounting_treatment": n.accounting_treatment,
                }
                for n in self.non_standard_clauses
            ],
            "ambiguous_expressions": [
                {
                    "expression": a.expression,
                    "ambiguity_type": a.ambiguity_type,
                    "possible_interpretations": a.possible_interpretations,
                    "recommended_clarification": a.recommended_clarification,
                }
                for a in self.ambiguous_expressions
            ],
            "all_risk_items": [
                {
                    "risk_level": r.risk_level.value,
                    "risk_category": r.risk_category.value,
                    "title": r.title,
                    "description": r.description,
                    "clause_reference": r.clause_reference,
                    "location": r.location,
                    "accounting_impact": r.accounting_impact,
                    "recommendation": r.recommendation,
                    "confidence": r.confidence,
                }
                for r in self.all_risk_items
            ],
            "accounting_notes": self.accounting_notes,
            "revenue_recognition_considerations": self.revenue_recognition_considerations,
            "provision_requirements": self.provision_requirements,
            "total_clauses_analyzed": self.total_clauses_analyzed,
            "risk_clauses_found": self.risk_clauses_found,
            "analysis_time": self.analysis_time.isoformat(),
        }


class ContractDeepAnalyzer:
    """
    合同深度分析器
    
    功能描述：超越字段提取，对合同进行语义理解与风险识别
    业务逻辑：
        1. 条款矛盾检测：识别合同中相互矛盾的条款
        2. 关键要素缺失预警：检测合同必备要素是否完整
        3. 非标条款风险标记：识别与标准合同偏离的条款
        4. 模糊表述识别：识别可能产生歧义的表述
        5. 会计处理建议：基于分析结果提供会计处理建议
    
    会计口径：
        - 符合CAS 14收入准则五步法模型
        - 识别可能影响收入确认的条款
        - 识别可能产生预计负债的违约条款
        - 识别可能产生金融资产风险的付款条款
    """
    
    def __init__(self):
        # 标准合同必备要素清单
        self.required_elements = {
            "basic_info": [
                ("contract_no", "合同编号", "critical"),
                ("contract_name", "合同名称", "high"),
                ("party_a_name", "甲方名称", "critical"),
                ("party_b_name", "乙方名称", "critical"),
                ("sign_date", "签订日期", "high"),
            ],
            "subject": [
                ("contract_subject", "合同标的", "critical"),
            ],
            "price": [
                ("contract_amount", "合同金额", "critical"),
                ("payment_terms", "付款条款", "high"),
            ],
            "period": [
                ("effective_date", "生效日期", "high"),
                ("expiry_date", "终止日期", "high"),
            ],
            "liability": [
                ("penalty_clause", "违约责任", "medium"),
            ],
        }
        
        # 常见矛盾模式
        self.contradiction_patterns = [
            (
                r"不可撤销", r"可撤销",
                "效力矛盾", "合同同时出现'不可撤销'和'可撤销'表述，需确认合同效力",
                RiskLevel.HIGH,
            ),
            (
                r"无条件", r"有条件|附条件",
                "条件矛盾", "合同同时出现'无条件'和'附条件'表述，需确认履约条件",
                RiskLevel.HIGH,
            ),
            (
                r"全额支付", r"部分支付|按比例",
                "付款矛盾", "合同同时出现'全额支付'和'部分支付'表述，需确认付款方式",
                RiskLevel.HIGH,
            ),
            (
                r"无需承担", r"承担责任",
                "责任矛盾", "合同同时出现'无需承担'和'承担责任'表述，需确认责任划分",
                RiskLevel.HIGH,
            ),
            (
                r"立即生效", r"另行约定生效",
                "生效矛盾", "合同同时出现'立即生效'和'另行约定生效'表述，需确认生效时间",
                RiskLevel.MEDIUM,
            ),
        ]
        
        # 非标条款模式
        self.non_standard_patterns = [
            (
                r"背靠背|背对背",
                "付款条款",
                "背靠背付款条款：上游付款后才向下游付款，可能产生收入确认延迟风险",
                RiskLevel.HIGH,
                "需评估是否存在重大融资成分，收入确认可能需调整",
            ),
            (
                r"最终解释权归.*所有",
                "解释权条款",
                "单方面最终解释权条款可能被认定为格式条款，存在法律风险",
                RiskLevel.MEDIUM,
                "建议获取法律意见确认条款效力",
            ),
            (
                r"以实际发生为准",
                "计量条款",
                "以实际发生为准的计量方式可能导致交易价格不确定",
                RiskLevel.MEDIUM,
                "需评估可变对价的确认条件",
            ),
            (
                r"无固定期限|长期有效",
                "期限条款",
                "无固定期限合同可能影响收入确认期间的判断",
                RiskLevel.LOW,
                "需评估收入确认的持续评估要求",
            ),
            (
                r"违约金.*过高|违约金.*过低",
                "违约金条款",
                "违约金过高或过低可能被法院调整，影响预计负债计量",
                RiskLevel.MEDIUM,
                "需评估预计负债的最佳估计金额",
            ),
            (
                r"有权单方解除|随时解除",
                "解除条款",
                "单方解除权可能影响合同的可执行性评估",
                RiskLevel.MEDIUM,
                "需评估合同资产的减值风险",
            ),
        ]
        
        # 模糊表述模式
        self.ambiguity_patterns = [
            (
                r"合理期限|适当期限|合理时间",
                "时间表述模糊",
                ["法院认定的合理期限", "行业惯例期限", "双方协商确定"],
                "建议明确具体期限",
            ),
            (
                r"相关费用|相应费用|合理费用",
                "费用表述模糊",
                ["实际发生的全部费用", "合同约定范围内的费用", "双方确认的费用"],
                "建议明确费用范围和承担方式",
            ),
            (
                r"同等条件下|同等对待",
                "条件表述模糊",
                ["相同价格条件", "相同付款条件", "相同全部条款"],
                "建议明确同等条件的具体内容",
            ),
            (
                r"重大损失|严重后果",
                "损失表述模糊",
                ["实际发生的损失", "预计可能发生的损失", "法院认定的损失"],
                "建议明确损失的计量方法",
            ),
        ]
    
    def analyze(
        self,
        raw_text: str,
        parsed_data: dict[str, Any],
    ) -> ContractDeepAnalysisResult:
        """
        执行合同深度分析
        
        Args:
            raw_text: 合同原始文本
            parsed_data: 结构化解析结果
            
        Returns:
            ContractDeepAnalysisResult: 深度分析结果
        """
        contradictions = self._detect_contradictions(raw_text)
        missing_elements = self._detect_missing_elements(parsed_data)
        non_standard_clauses = self._detect_non_standard_clauses(raw_text)
        ambiguous_expressions = self._detect_ambiguity(raw_text)
        
        all_risk_items = self._consolidate_risk_items(
            contradictions,
            missing_elements,
            non_standard_clauses,
            ambiguous_expressions,
        )
        risk_score = min(100.0, len(all_risk_items) * 8.0)
        overall = RiskLevel.INFO
        if risk_score >= 60:
            overall = RiskLevel.CRITICAL
        elif risk_score >= 40:
            overall = RiskLevel.HIGH
        elif risk_score >= 20:
            overall = RiskLevel.MEDIUM
        elif risk_score >= 8:
            overall = RiskLevel.LOW

        return ContractDeepAnalysisResult(
            overall_risk_level=overall,
            risk_score=risk_score,
            analysis_summary=f"识别风险项 {len(all_risk_items)} 条；缺失要素 {len(missing_elements)} 项",
            contradictions=contradictions,
            missing_elements=missing_elements,
            non_standard_clauses=non_standard_clauses,
            ambiguous_expressions=ambiguous_expressions,
            all_risk_items=all_risk_items,
            accounting_notes="请结合合同标的、付款与涉税条款复核收入/成本确认时点",
            revenue_recognition_considerations="关注可变对价、背靠背付款及履约义务拆分",
            provision_requirements="关注违约金与或有事项披露",
            total_clauses_analyzed=max(1, len(raw_text.split("\n"))),
            risk_clauses_found=len(all_risk_items),
        )

    def _detect_contradictions(self, raw_text: str) -> list[ClauseContradiction]:
        import re

        results: list[ClauseContradiction] = []
        for pattern_a, pattern_b, ctype, desc, level in self.contradiction_patterns:
            if re.search(pattern_a, raw_text) and re.search(pattern_b, raw_text):
                results.append(
                    ClauseContradiction(
                        clause_a=pattern_a,
                        clause_b=pattern_b,
                        contradiction_type=ctype,
                        description=desc,
                        risk_level=level,
                    )
                )
        return results

    def _detect_missing_elements(self, parsed_data: dict[str, Any]) -> list[MissingElement]:
        missing: list[MissingElement] = []
        for _cat, elements in self.required_elements.items():
            for field_key, label, importance in elements:
                value = parsed_data.get(field_key)
                if value is None or (isinstance(value, str) and not value.strip()):
                    missing.append(
                        MissingElement(
                            element_name=label,
                            element_category=_cat,
                            importance=importance,
                            description=f"结构化解析未提取到「{label}」",
                            suggested_action="人工补录或增强解析规则/LLM 提取",
                        )
                    )
        return missing

    def _detect_non_standard_clauses(self, raw_text: str) -> list[NonStandardClause]:
        import re

        results: list[NonStandardClause] = []
        for pattern, clause_type, risk_desc, level, accounting in self.non_standard_patterns:
            match = re.search(pattern, raw_text)
            if match:
                results.append(
                    NonStandardClause(
                        clause_text=match.group(0)[:200],
                        clause_type=clause_type,
                        deviation_from_standard="偏离常见标准合同表述",
                        risk_description=risk_desc,
                        risk_level=level,
                        accounting_treatment=accounting,
                    )
                )
        return results

    def _detect_ambiguity(self, raw_text: str) -> list[AmbiguousExpression]:
        import re

        results: list[AmbiguousExpression] = []
        for pattern, amb_type, interpretations, recommendation in self.ambiguity_patterns:
            match = re.search(pattern, raw_text)
            if match:
                results.append(
                    AmbiguousExpression(
                        expression=match.group(0),
                        ambiguity_type=amb_type,
                        possible_interpretations=list(interpretations),
                        recommended_clarification=recommendation,
                    )
                )
        return results

    def _consolidate_risk_items(
        self,
        contradictions: list[ClauseContradiction],
        missing_elements: list[MissingElement],
        non_standard_clauses: list[NonStandardClause],
        ambiguous_expressions: list[AmbiguousExpression],
    ) -> list[ContractRiskItem]:
        items: list[ContractRiskItem] = []
        for c in contradictions:
            items.append(
                ContractRiskItem(
                    risk_level=c.risk_level,
                    risk_category=RiskCategory.CONTRADICTION,
                    title=c.contradiction_type,
                    description=c.description,
                    clause_reference=f"{c.clause_a} vs {c.clause_b}",
                )
            )
        for m in missing_elements:
            level = RiskLevel.CRITICAL if m.importance == "critical" else RiskLevel.HIGH
            items.append(
                ContractRiskItem(
                    risk_level=level,
                    risk_category=RiskCategory.MISSING_ELEMENT,
                    title=m.element_name,
                    description=m.description,
                    recommendation=m.suggested_action,
                )
            )
        for n in non_standard_clauses:
            items.append(
                ContractRiskItem(
                    risk_level=n.risk_level,
                    risk_category=RiskCategory.NON_STANDARD,
                    title=n.clause_type,
                    description=n.risk_description,
                    accounting_impact=n.accounting_treatment,
                )
            )
        for a in ambiguous_expressions:
            items.append(
                ContractRiskItem(
                    risk_level=RiskLevel.MEDIUM,
                    risk_category=RiskCategory.AMBIGUITY,
                    title=a.ambiguity_type,
                    description=a.expression,
                    recommendation=a.recommended_clarification,
                )
            )
        return items
