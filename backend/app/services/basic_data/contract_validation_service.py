# -*- coding: utf-8 -*-
"""
模块功能：合同字段完整性校验与 LLM 推理补全服务
业务场景：在合同解析后，对关键字段进行完整性校验；对少量缺失字段基于
         已有合同数据进行可溯源的 LLM 推理补全。
校验规则：
    - 必填字段缺失超过 2 个：标记为需人工干预
    - 1-2 个缺失：尝试 LLM 推理补全
    - payment_terms 若传入对象/字典，转换为文本描述
输出：包含校验结果、推理过程、最终状态的报告对象
"""

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.services.agent.llm_client_service import LightweightLLMClient, LLMResult
from app.services.basic_data.contract_parser_service import (
    ContractParseResult,
    CommodityItem,
    ContractParty,
    ContractPrice,
    TaxLiabilityClause,
    TaxTreatment,
)


REQUIRED_FIELDS = [
    "contract_name",
    "party_a_name",
    "party_b_name",
    "sign_date",
    "contract_amount",
    "contract_amount_cn",
    "contract_term",
    "contract_type",
    "payment_terms",
]

OPTIONAL_FIELDS = [
    "contract_no",
    "party_a_tax_id",
    "party_a_address",
    "party_b_tax_id",
    "party_b_address",
    "project_name",
    "liability_clause",
]


@dataclass
class FieldInference:
    """单个字段的推理记录"""
    field_name: str
    original_value: Any = None
    inferred_value: Any = None
    reasoning: str = ""
    confidence: str = "high"  # high / medium / low


@dataclass
class ContractValidationReport:
    """合同校验与推理报告"""
    success: bool = False
    status: str = ""  # success_with_inference / manual_intervention_required
    missing_required_fields: list[str] = field(default_factory=list)
    missing_optional_fields: list[str] = field(default_factory=list)
    present_fields: list[str] = field(default_factory=list)
    inferences: list[FieldInference] = field(default_factory=list)
    inference_summary: str = ""
    final_data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    raw_llm_response: str = ""


@dataclass
class ComplianceDimension:
    """合规评分维度"""
    name: str = ""
    weight: int = 0  # 权重百分比
    score: int = 100  # 该维度得分 0-100
    findings: list[str] = field(default_factory=list)


@dataclass
class ProcurementComplianceReport:
    """采购合同合规性评分报告"""
    overall_score: int = 100
    risk_level: str = "low"  # high / medium / low
    extraction_score: int = 100
    compliance_score: int = 100
    dimensions: list[ComplianceDimension] = field(default_factory=list)
    missing_clauses: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    internal_control_notes: str = ""
    recommendations: list[str] = field(default_factory=list)


class ContractValidationService:
    """合同字段校验与 LLM 推理服务"""

    def __init__(self, llm_client: LightweightLLMClient | None = None):
        self.llm = llm_client or LightweightLLMClient()

    def _is_empty(self, value: Any) -> bool:
        """判断字段是否为空（未提供或无效）"""
        if value is None:
            return True
        if isinstance(value, str) and value.strip() == "":
            return True
        if isinstance(value, (list, dict)) and len(value) == 0:
            return True
        return False

    def _normalize_payment_terms(self, value: Any) -> tuple[Any, bool]:
        """
        将 payment_terms 统一为文本描述。
        若传入 dict / list，转换为人类可读的文本；若已是非空字符串则原样返回。
        """
        if self._is_empty(value):
            return None, True
        if isinstance(value, str):
            return value.strip(), False
        if isinstance(value, dict):
            parts = []
            for k, v in value.items():
                parts.append(f"{k}: {v}")
            return "；".join(parts), True if parts else False
        if isinstance(value, list):
            items = []
            for item in value:
                if isinstance(item, dict):
                    items.append("；".join(f"{k}: {v}" for k, v in item.items()))
                else:
                    items.append(str(item))
            return " | ".join(items), True if items else False
        return str(value), True

    def _number_to_chinese(self, amount: Decimal | float | int | str | None) -> str:
        """
        将数字金额转换为大写中文金额（用于 contract_amount_cn 推理兜底）。
        实际推理优先使用 LLM；本方法作为本地快速回退。
        """
        if amount is None:
            return ""
        try:
            value = Decimal(str(amount))
        except Exception:
            return ""

        if value < 0:
            return ""

        nums = ["零", "壹", "贰", "叁", "肆", "伍", "陆", "柒", "捌", "玖"]
        units = ["", "拾", "佰", "仟"]
        big_units = ["", "万", "亿", "万亿"]

        integer_part = int(value)
        decimal_part = int((value - integer_part) * 100)

        def _four_to_chinese(n: int) -> str:
            """将 0-9999 的整数转为中文（四位一段）"""
            s = str(n).zfill(4)
            res = ""
            for i, ch in enumerate(s):
                d = int(ch)
                pos = 3 - i
                if d == 0:
                    if res and not res.endswith("零"):
                        res += "零"
                else:
                    res += nums[d] + units[pos]
            return res.rstrip("零")

        if integer_part == 0:
            integer_cn = "零"
        else:
            sections: list[int] = []
            n = integer_part
            while n > 0:
                sections.append(n % 10000)
                n //= 10000

            sec_cns: list[str] = []
            for i, sec in enumerate(sections):
                if sec == 0:
                    sec_cns.append("")
                else:
                    cn = _four_to_chinese(sec)
                    if i > 0:
                        cn += big_units[i]
                    sec_cns.append(cn)

            # 从高到低拼接，自动补零
            integer_cn = ""
            for i in range(len(sec_cns) - 1, -1, -1):
                if not sec_cns[i]:
                    if integer_cn and not integer_cn.endswith("零"):
                        integer_cn += "零"
                    continue
                # 低位段存在隐含前导零时需要补零
                if (
                    integer_cn
                    and not integer_cn.endswith("零")
                    and i > 0
                    and sections[i] < 1000
                ):
                    integer_cn += "零"
                integer_cn += sec_cns[i]

            integer_cn = re.sub(r"零+", "零", integer_cn)
            integer_cn = integer_cn.rstrip("零")

        integer_cn += "元"

        jiao = decimal_part // 10
        fen = decimal_part % 10
        decimal_cn = ""
        if jiao > 0:
            decimal_cn += nums[jiao] + "角"
        if fen > 0:
            decimal_cn += nums[fen] + "分"
        if not decimal_cn:
            decimal_cn = "整"

        return integer_cn + decimal_cn

    def _build_inference_prompt(self, contract_data: dict[str, Any], missing_fields: list[str]) -> list[dict[str, Any]]:
        """构建用于推理缺失字段的 LLM 提示词"""
        system_prompt = """你是一位专业的财务合同审查助手。请根据已提供的合同字段，通过逻辑推理补全 1-2 个缺失字段。

要求：
1. 只补全用户指定的缺失字段，不要编造不存在的信息。
2. 每个推理必须有明确、可追溯的依据，说明是基于哪个已有字段推导出来的。
3. 保持商业合理性和法律合理性；无法合理推断时明确说明无法推断。
4. 对于 contract_amount_cn（大写金额），请基于 contract_amount 的数值给出标准财务大写金额。
5. 对于 contract_term（合同期限/期限描述），请基于 start_date、end_date、sign_date 或合同名称中的时间线索推导；若无法推导请说明。
6. 对于 payment_terms（付款条款），请基于已有字段中的付款描述、分期信息、背靠背条款等整理为一段通顺的中文文本描述。
7. 输出必须是合法的 JSON，不要包含任何其他文字。

输出格式：
{
  "inferences": [
    {
      "field_name": "字段名",
      "inferred_value": "补全后的值",
      "reasoning": "推理依据，必须引用已有字段",
      "confidence": "high/medium/low"
    }
  ],
  "uninferable_fields": ["无法推断的字段名"],
  "notes": "额外说明"
}"""

        user_prompt = f"""已知合同字段：
{json.dumps(contract_data, ensure_ascii=False, indent=2, default=str)}

需要补全的缺失字段：{json.dumps(missing_fields, ensure_ascii=False)}

请严格按上述要求输出 JSON。"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _parse_inference_response(self, response: LLMResult) -> tuple[list[FieldInference], list[str], str]:
        """解析 LLM 推理响应"""
        inferences: list[FieldInference] = []
        uninferable: list[str] = []
        notes = ""

        if not response.available or not response.content:
            return inferences, uninferable, f"LLM 推理不可用：{response.error or '无响应'}"

        content = response.content.strip()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    return inferences, uninferable, f"LLM 返回格式错误：{content[:200]}"
            else:
                return inferences, uninferable, f"LLM 返回格式错误：{content[:200]}"

        for item in data.get("inferences", []):
            inferences.append(
                FieldInference(
                    field_name=item.get("field_name", ""),
                    inferred_value=item.get("inferred_value"),
                    reasoning=item.get("reasoning", ""),
                    confidence=item.get("confidence", "medium"),
                )
            )
        uninferable = data.get("uninferable_fields", [])
        notes = data.get("notes", "")

        return inferences, uninferable, notes

    def validate_and_infer(
        self,
        contract_data: dict[str, Any],
        allow_llm_inference: bool = True,
    ) -> ContractValidationReport:
        """
        主入口：校验合同字段完整性，并对 1-2 个缺失必填字段进行 LLM 推理补全。

        Args:
            contract_data: 合同原始/解析后数据字典
            allow_llm_inference: 是否允许使用 LLM 推理；False 时只做校验

        Returns:
            ContractValidationReport: 包含校验、推理、最终状态及最终数据的报告
        """
        report = ContractValidationReport()
        data: dict[str, Any] = {k: v for k, v in contract_data.items()}

        # 1. 预处理 payment_terms：对象/列表转文本
        payment_value, _ = self._normalize_payment_terms(data.get("payment_terms"))
        if payment_value is not None:
            data["payment_terms"] = payment_value
        else:
            data["payment_terms"] = None

        # 2. 字段完整性校验
        missing_required = []
        present_fields = []
        for field_name in REQUIRED_FIELDS:
            if self._is_empty(data.get(field_name)):
                missing_required.append(field_name)
            else:
                present_fields.append(field_name)

        missing_optional = [
            f for f in OPTIONAL_FIELDS if self._is_empty(data.get(f))
        ]

        report.missing_required_fields = missing_required
        report.missing_optional_fields = missing_optional
        report.present_fields = present_fields
        report.final_data = dict(data)

        # 3. 缺失必填字段 > 2：直接失败
        if len(missing_required) > 2:
            report.success = False
            report.status = "manual_intervention_required"
            report.errors.append(
                f"缺失必填字段 {len(missing_required)} 个，超过允许推理上限 2 个："
                f"{', '.join(missing_required)}"
            )
            return report

        # 4. 无缺失：直接成功
        if not missing_required:
            report.success = True
            report.status = "success_with_inference"
            report.inference_summary = "所有必填字段完整，无需推理。"
            return report

        # 5. 1-2 个缺失：尝试 LLM 推理
        if not allow_llm_inference or not self.llm.is_configured():
            report.success = False
            report.status = "manual_intervention_required"
            report.errors.append(
                "存在缺失必填字段，但 LLM 推理未启用或未配置，需人工干预。"
            )
            return report

        messages = self._build_inference_prompt(data, missing_required)
        response = self.llm.chat(messages, temperature=0.1)
        report.raw_llm_response = response.content or response.error or ""

        inferences, uninferable, notes = self._parse_inference_response(response)
        report.inferences = inferences
        report.inference_summary = notes

        # 应用推理结果到 final_data
        inferred_field_names = set()
        for inf in inferences:
            if inf.field_name and inf.inferred_value is not None:
                report.final_data[inf.field_name] = inf.inferred_value
                inferred_field_names.add(inf.field_name)

        # 对 contract_amount_cn 做本地兜底：仅当 LLM 正常返回但遗漏该字段时，
        # 基于 contract_amount 自动转换；LLM 不可用时不能视为有明确推理。
        if (
            response.available
            and "contract_amount_cn" in missing_required
            and "contract_amount_cn" not in inferred_field_names
        ):
            amount = report.final_data.get("contract_amount")
            if not self._is_empty(amount):
                report.final_data["contract_amount_cn"] = self._number_to_chinese(amount)
                report.inferences.append(
                    FieldInference(
                        field_name="contract_amount_cn",
                        inferred_value=report.final_data["contract_amount_cn"],
                        reasoning=f"基于 contract_amount={amount} 进行标准财务大写金额转换",
                        confidence="high",
                    )
                )
                inferred_field_names.add("contract_amount_cn")

        # 6. 最终校验
        still_missing = [
            f for f in missing_required if self._is_empty(report.final_data.get(f))
        ]

        if still_missing:
            report.success = False
            report.status = "manual_intervention_required"
            report.errors.append(
                f"以下必填字段无法通过推理补全，需人工干预：{', '.join(still_missing)}"
            )
            if uninferable:
                report.errors.append(f"LLM 明确无法推断的字段：{', '.join(uninferable)}")
        else:
            report.success = True
            report.status = "success_with_inference"
            report.inference_summary = (
                notes or f"通过 LLM 推理补全字段：{', '.join(inferred_field_names)}"
            )

        return report

    def format_report_text(self, report: ContractValidationReport) -> str:
        """将报告格式化为可读的文本摘要"""
        lines = [
            "=== 合同字段校验与推理报告 ===",
            f"最终状态：{'成功' if report.success else '需人工干预'}",
            f"状态标记：{report.status}",
            f"已填必填字段：{', '.join(report.present_fields) or '无'}",
            f"缺失必填字段：{', '.join(report.missing_required_fields) or '无'}",
            f"缺失选填字段：{', '.join(report.missing_optional_fields) or '无'}",
            "",
            "推理过程：",
        ]
        if report.inferences:
            for inf in report.inferences:
                lines.append(
                    f"  - {inf.field_name}: {inf.inferred_value} "
                    f"(置信度：{inf.confidence})"
                )
                lines.append(f"    依据：{inf.reasoning}")
        else:
            lines.append("  无")

        if report.errors:
            lines.append("")
            lines.append("错误/提示：")
            for err in report.errors:
                lines.append(f"  - {err}")

        lines.append("")
        lines.append(f"推理摘要：{report.inference_summary or '无'}")
        return "\n".join(lines)

    # ============== 采购合同合规性评分 ==============

    def assess_procurement_compliance(
        self, result: ContractParseResult, extraction_score: int = 100
    ) -> ProcurementComplianceReport:
        """
        对采购合同解析结果进行合规性评分。

        评分维度（权重合计 100%）：
        - 主体完整性（15%）：甲乙双方名称、税号、地址、银行账户
        - 标的明确性（20%）：商品名称、规格、型号、数量、质量标准
        - 价格与支付（20%）：总价、分项费用、税率、付款条件
        - 交付与验收（15%）：交货期、地点、验收标准、异议期
        - 税务责任（15%）：开票义务、税负承担、发票类型
        - 违约与争议（15%）：违约责任、质保、争议解决

        Args:
            result: ContractParser 解析结果
            extraction_score: 解析完整性得分（0-100）

        Returns:
            ProcurementComplianceReport: 合规评分报告
        """
        report = ProcurementComplianceReport(extraction_score=extraction_score)
        dimensions: list[ComplianceDimension] = []

        # 1. 主体完整性
        dim_party = self._assess_party_compliance(result)
        dimensions.append(dim_party)

        # 2. 标的明确性
        dim_commodity = self._assess_commodity_compliance(result)
        dimensions.append(dim_commodity)

        # 3. 价格与支付
        dim_price = self._assess_price_compliance(result)
        dimensions.append(dim_price)

        # 4. 交付与验收
        dim_delivery = self._assess_delivery_compliance(result)
        dimensions.append(dim_delivery)

        # 5. 税务责任
        dim_tax = self._assess_tax_compliance(result)
        dimensions.append(dim_tax)

        # 6. 违约与争议
        dim_penalty = self._assess_penalty_compliance(result)
        dimensions.append(dim_penalty)

        report.dimensions = dimensions

        # 计算加权合规得分
        total_weight = sum(d.weight for d in dimensions)
        if total_weight == 0:
            report.compliance_score = 100
        else:
            report.compliance_score = int(
                round(sum(d.score * d.weight for d in dimensions) / total_weight)
            )

        # 汇总缺失条款与风险标记
        for dim in dimensions:
            report.missing_clauses.extend(dim.findings)

        # 税务责任重大风险标记：仅在重大税务责任条款存在缺陷时标记
        if result.tax_liability.is_critical:
            has_tax_risk = False
            if not result.tax_liability.responsible_party:
                has_tax_risk = True
            if result.tax_liability.tax_rate > 0 and not result.tax_liability.invoice_type:
                has_tax_risk = True
            if (
                result.tax_liability.tax_rate > 0
                and result.tax_treatment.tax_rate > 0
                and result.tax_liability.tax_rate != result.tax_treatment.tax_rate
            ):
                has_tax_risk = True
                report.risk_flags.append(
                    f"税务责任税率({result.tax_liability.tax_rate})"
                    f"与税务处理税率({result.tax_treatment.tax_rate})不一致"
                )
            if has_tax_risk:
                report.risk_flags.append("重大税务责任条款存在缺陷")

        # 商品勾稽风险
        for commodity in result.commodities:
            if commodity.consistency_errors:
                report.risk_flags.append(
                    f"商品{commodity.item_no}存在一致性错误：{commodity.consistency_errors}"
                )
            if commodity.missing_attributes:
                report.risk_flags.append(
                    f"商品{commodity.item_no}缺失属性：{commodity.missing_attributes}"
                )

        # 计算综合得分：提取得分与合规得分各占 50%
        report.overall_score = int(round((extraction_score + report.compliance_score) / 2))

        # 风险等级：综合合规得分、解析完整性与风险标记
        if report.compliance_score < 60 or extraction_score < 60:
            report.risk_level = "high"
        elif (
            report.risk_flags
            or report.compliance_score < 80
            or (extraction_score < 90 and report.missing_clauses)
        ):
            report.risk_level = "medium"
        else:
            report.risk_level = "low"

        # 内控初步评价与建议
        report.internal_control_notes = self._build_internal_control_notes(report)
        report.recommendations = self._build_recommendations(report)

        return report

    def _assess_party_compliance(self, result: ContractParseResult) -> ComplianceDimension:
        """评估合同主体完整性"""
        dim = ComplianceDimension(name="主体完整性", weight=15)
        score = 100

        if not result.parties:
            score -= 50
            dim.findings.append("未识别到合同主体")
            dim.score = max(0, score)
            return dim

        party_names = [p.name for p in result.parties if p.name]
        if len(party_names) < 2:
            score -= 30
            dim.findings.append("合同主体不足两方")

        for party in result.parties:
            if not party.name:
                score -= 10
                dim.findings.append("存在主体名称缺失")
            if not party.tax_id:
                score -= 5
                dim.findings.append(f"{party.role or '某方'}缺少纳税人识别号")
            if not party.address:
                score -= 5
                dim.findings.append(f"{party.role or '某方'}缺少地址")

        dim.score = max(0, score)
        return dim

    def _assess_commodity_compliance(self, result: ContractParseResult) -> ComplianceDimension:
        """评估标的明确性"""
        dim = ComplianceDimension(name="标的明确性", weight=20)
        score = 100

        if result.contract_type.lower() in ("procurement", "purchase", "采购"):
            if not result.commodities:
                score -= 40
                dim.findings.append("采购合同未识别商品明细")
            else:
                for commodity in result.commodities:
                    if not commodity.product_name:
                        score -= 10
                        dim.findings.append(f"商品{commodity.item_no}缺少产品名称")
                    if not commodity.specification:
                        score -= 5
                        dim.findings.append(f"商品{commodity.item_no}缺少规格参数")
                    if not commodity.model_number:
                        # 设备/电子类商品更严格
                        if any(
                            keyword in commodity.product_name
                            for keyword in ("设备", "机器", "仪器", "电脑", "服务器")
                        ):
                            score -= 10
                            dim.findings.append(f"设备类商品{commodity.item_no}缺少型号")
                        else:
                            score -= 3
                    if commodity.quantity <= 0:
                        score -= 10
                        dim.findings.append(f"商品{commodity.item_no}数量异常")
                    if commodity.unit_price <= 0:
                        score -= 10
                        dim.findings.append(f"商品{commodity.item_no}单价异常")
                    if not commodity.quality_standard:
                        score -= 5
                        dim.findings.append(f"商品{commodity.item_no}缺少质量标准")

        dim.score = max(0, score)
        return dim

    def _assess_price_compliance(self, result: ContractParseResult) -> ComplianceDimension:
        """评估价格与支付合规性"""
        dim = ComplianceDimension(name="价格与支付", weight=20)
        score = 100

        if result.price.total_amount <= 0 and result.financial_terms.contract_amount <= 0:
            score -= 40
            dim.findings.append("合同总价未明确")
        if not result.price.payment_terms:
            score -= 15
            dim.findings.append("缺少付款条件")
        if result.price.tax_rate <= 0 and result.financial_terms.tax_rate is None:
            score -= 15
            dim.findings.append("税率未明确")

        # 未明确重大费用
        critical_fees = ["transportation_fee", "warehousing_cost", "insurance_fee"]
        for fee_attr in critical_fees:
            fee_value = getattr(result.financial_terms, fee_attr)
            if fee_value is None and fee_attr not in result.financial_terms.explicitly_stated:
                # 基于合同金额判断该费用是否重大（超过 5% 视为重大）
                total = max(result.price.total_amount, result.financial_terms.contract_amount)
                if total > 0:
                    # 保守估算占 3-7%，若可能重大则扣分
                    # 按上限 7% 估算，超过 5% 阈值则视为可能重大
                    potential_fee = total * Decimal("0.07")
                    if potential_fee / total > Decimal("0.05"):
                        score -= 5
                        dim.findings.append(f"{fee_attr}未明确且可能重大")

        dim.score = max(0, score)
        return dim

    def _assess_delivery_compliance(self, result: ContractParseResult) -> ComplianceDimension:
        """评估交付与验收合规性"""
        dim = ComplianceDimension(name="交付与验收", weight=15)
        score = 100

        if not result.period.start_date and not result.period.end_date:
            score -= 20
            dim.findings.append("缺少合同履行期限")

        has_delivery_terms = any(
            c.delivery_terms for c in result.commodities
        ) or "delivery" in result.summary.lower()
        if not has_delivery_terms:
            score -= 15
            dim.findings.append("缺少交货地点/方式条款")

        has_acceptance = any(
            c.quality_standard for c in result.commodities
        ) or "验收" in result.summary
        if not has_acceptance:
            score -= 15
            dim.findings.append("缺少验收标准或异议期条款")

        dim.score = max(0, score)
        return dim

    def _assess_tax_compliance(self, result: ContractParseResult) -> ComplianceDimension:
        """评估税务责任合规性"""
        dim = ComplianceDimension(name="税务责任", weight=15)
        score = 100

        if not result.tax_liability.is_critical and not result.tax_liability.full_text:
            score -= 20
            dim.findings.append("缺少税务责任专项条款")

        if result.tax_liability.is_critical:
            if not result.tax_liability.responsible_party:
                score -= 10
                dim.findings.append("重大税务责任条款未明确责任方")
            if result.tax_liability.tax_rate > 0 and not result.tax_liability.invoice_type:
                score -= 10
                dim.findings.append("税务责任条款约定税率但未明确发票类型")

        # 税率一致性
        if (
            result.tax_liability.tax_rate > 0
            and result.tax_treatment.tax_rate > 0
            and result.tax_liability.tax_rate != result.tax_treatment.tax_rate
        ):
            score -= 15
            dim.findings.append("税务责任条款税率与税务处理税率不一致")

        dim.score = max(0, score)
        return dim

    def _assess_penalty_compliance(self, result: ContractParseResult) -> ComplianceDimension:
        """评估违约与争议解决合规性"""
        dim = ComplianceDimension(name="违约与争议", weight=15)
        score = 100

        if not result.penalties:
            score -= 20
            dim.findings.append("缺少违约责任条款")
        else:
            for penalty in result.penalties:
                if not penalty.penalty_clause:
                    score -= 5
                    dim.findings.append("违约责任条款原文缺失")

        has_warranty = any(c.warranty_period for c in result.commodities)
        if not has_warranty and result.contract_type.lower() in (
            "procurement", "purchase", "采购"
        ):
            score -= 10
            dim.findings.append("采购合同缺少质保期条款")

        dim.score = max(0, score)
        return dim

    def _build_internal_control_notes(self, report: ProcurementComplianceReport) -> str:
        """生成内控初步评价"""
        if report.risk_level == "low":
            return (
                f"合同整体合规性良好（得分{report.overall_score}），"
                "关键条款基本完整，内部控制风险较低。"
            )
        if report.risk_level == "medium":
            return (
                f"合同存在一定合规瑕疵（得分{report.overall_score}），"
                f"存在 {len(report.missing_clauses)} 项缺失/风险点，建议补充相关条款后复核。"
            )
        return (
            f"合同合规性较差（得分{report.overall_score}），"
            f"存在 {len(report.missing_clauses)} 项重要缺失或 {len(report.risk_flags)} 项风险标记，"
            "建议在签署前进行法律/合规专项审查。"
        )

    def _build_recommendations(self, report: ProcurementComplianceReport) -> list[str]:
        """生成改进建议"""
        recommendations = []
        for finding in report.missing_clauses:
            if "缺少" in finding and "专项条款" not in finding:
                recommendations.append(f"补充{finding.replace('缺少', '')}")
            elif "缺失" in finding:
                recommendations.append(f"完善{finding.replace('缺失', '')}")

        if report.risk_flags:
            recommendations.append("对标记的风险点进行专项复核")
        if report.compliance_score < 60 or report.overall_score < 60:
            recommendations.append("建议退回业务部门补充合同条款")

        return recommendations
