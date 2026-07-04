# -*- coding: utf-8 -*-
"""
模块功能：合同解析服务（ContractParser）- 基于 CAS 14 收入准则 + 采购合同合规审查
业务场景：AI 生成凭证 Step 2 中，对 PDF 合同文件进行结构化解析
政策依据：
    - 企业会计准则第 14 号——收入（五步法模型）
    - 企业会计准则第 13 号——或有事项（违约责任预提）
    - 企业会计准则第 22 号——金融工具确认和计量（预期信用损失）
    - 财税〔2016〕36 号（增值税价税分离）
输入数据：PDF 合同文本（已通过 OCR 或 pdfplumber 提取）
输出结果：结构化合同信息（JSON），包含收入确认、成本、金融、税务、或有事项五大维度
         同时包含采购合同商品明细、财务条款、税务责任条款及合规评估元数据
创建日期：2026-06-26
更新记录：
    2026-06-26  初始创建，支持 LLM 解析合同关键信息
    2026-06-26  完善 CAS 14 五步法参数，添加履约义务、时段法、交易价格等
    2026-07-02  扩展采购合同解析：商品明细、财务条款、税务责任、合规评估
"""

import json
import re
from dataclasses import dataclass, field, asdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from app.services.agent.llm_client_service import LightweightLLMClient, LLMResult


@dataclass
class ContractParty:
    """合同主体信息（对应 CAS 14 第五条：合同成立要件）"""
    name: str = ""              # 主体名称
    role: str = ""              # 角色：甲方、乙方、丙方、担保方等
    address: str = ""           # 注册地址
    contact: str = ""           # 联系人
    tax_id: str = ""            # 纳税人识别号
    legal_capacity: bool = True  # 是否具备民事行为能力


@dataclass
class ContractPeriod:
    """合同执行周期"""
    start_date: str = ""        # 开始日期（YYYY-MM-DD）
    end_date: str = ""          # 结束日期（YYYY-MM-DD）
    duration_days: int = 0      # 总天数
    is_indefinite: bool = False # 是否无固定期限
    termination_terms: str = "" # 终止条款


@dataclass
class ContractPrice:
    """交易价格信息（对应 CAS 14 第十四条至第十九条）"""
    total_amount: Decimal = Decimal("0.00")      # 含税总价
    amount_excl_tax: Decimal = Decimal("0.00")     # 不含税金额（交易价格）
    tax_rate: Decimal = Decimal("0.00")          # 税率（如 0.06）
    tax_amount: Decimal = Decimal("0.00")        # 税额
    currency: str = "CNY"                        # 币种
    
    # 可变对价（CAS 14 第十六条）
    variable_consideration: Decimal = Decimal("0.00")  # 可变对价金额
    variable_type: str = ""                            # 类型：奖励/罚款/折扣/绩效扣款
    variable_constraint: str = ""                      # 限制条件：极可能不会重大转回
    
    # 重大融资成分（CAS 14 第十七条）
    significant_financing: bool = False          # 是否存在重大融资成分
    discount_rate: Decimal = Decimal("0.00")     # 折现率
    
    # 非现金对价（CAS 14 第十八条）
    non_cash_consideration: Decimal = Decimal("0.00")  # 非现金对价公允价值
    
    # 应付客户对价（CAS 14 第十九条）
    payable_to_customer: Decimal = Decimal("0.00")     # 应付客户对价
    
    # 付款条款
    payment_terms: str = ""                      # 付款条款描述
    back_to_back: bool = False                   # 是否背靠背付款
    installment_schedule: list[dict[str, Any]] = field(default_factory=list)  # 分期付款计划


@dataclass
class PerformanceObligation:
    """单项履约义务（对应 CAS 14 第九条、第十条）"""
    item_no: int = 0                    # 序号
    description: str = ""               # 标的描述
    quantity: Decimal = Decimal("0")    # 数量
    unit: str = ""                      # 单位
    unit_price: Decimal = Decimal("0.00")  # 单价
    total_price: Decimal = Decimal("0.00")   # 小计
    
    # 可明确区分判断（CAS 14 第十条）
    distinct: bool = True               # 客户能否单独获益
    separately_identifiable: bool = True  # 承诺能否单独识别
    highly_interdependent: bool = False   # 是否高度关联/需要重大整合
    integration_service: bool = False     # 是否重大整合服务
    
    # 收入确认方法（CAS 14 第十一条、第十二条）
    revenue_recognition_method: str = ""  # 时段法/时点法
    time_method_criteria: list[str] = field(default_factory=list)  # 满足时段法条件
    qualified_payment_right: bool = False   # 是否拥有合格收款权
    irreplaceable_use: bool = False         # 是否具有不可替代用途
    
    # 单独售价（CAS 14 第二十条）
    standalone_selling_price: Decimal = Decimal("0.00")  # 单独售价
    allocation_ratio: Decimal = Decimal("0.00")        # 分摊比例


@dataclass
class ContractPenalty:
    """违约责任（对应 CAS 13 或有事项）"""
    penalty_clause: str = ""                    # 违约条款原文
    penalty_amount: Decimal = Decimal("0.00")   # 违约金金额
    penalty_type: str = ""                      # 类型：迟延/质量/其他
    is_probable: bool = False                   # 是否很可能发生
    provision_required: bool = False            # 是否需要预提（预计负债）
    provision_amount: Decimal = Decimal("0.00") # 预提金额
    impact_on_revenue: str = ""                 # 对收入确认的影响说明


@dataclass
class ContractCost:
    """合同成本（对应 CAS 14 第二十六条至第二十九条）"""
    cost_type: str = ""                         # 类型：取得成本/履约成本
    amount: Decimal = Decimal("0.00")           # 金额
    amortization_method: str = ""             # 摊销方法
    amortization_period: str = ""             # 摊销期间


@dataclass
class FinancialAssetInfo:
    """金融资产信息（对应 CAS 22）"""
    asset_type: str = ""                        # 应收账款/合同资产
    amount: Decimal = Decimal("0.00")         # 金额
    expected_credit_loss: Decimal = Decimal("0.00")  # 预期信用损失
    risk_rating: str = ""                       # 风险评级


@dataclass
class TaxTreatment:
    """税务处理"""
    tax_type: str = ""                          # 增值税/所得税
    tax_rate: Decimal = Decimal("0.00")       # 税率
    tax_amount: Decimal = Decimal("0.00")     # 税额
    tax_basis: str = ""                         # 计税基础
    special_treatment: str = ""                 # 特殊处理（如税负转嫁）


# ============== 采购合同扩展数据结构 ==============


@dataclass
class CommodityItem:
    """采购合同商品/货物明细"""
    item_no: int = 0                    # 序号
    product_name: str = ""              # 产品名称
    specification: str = ""             # 规格参数
    model_number: str = ""              # 型号
    brand: str = ""                     # 品牌/产地
    unit: str = ""                      # 计量单位
    quantity: Decimal = Decimal("0")    # 数量
    unit_price: Decimal = Decimal("0.00")  # 单价
    total_price: Decimal = Decimal("0.00") # 小计
    weight: str = ""                    # 重量参数
    quality_standard: str = ""          # 质量标准
    delivery_terms: str = ""            # 交货条款
    warranty_period: str = ""           # 质保期
    missing_attributes: list[str] = field(default_factory=list)  # 缺失属性标记
    consistency_errors: list[str] = field(default_factory=list)  # 一致性错误


@dataclass
class FeeEstimate:
    """未明确费用的保守估算"""
    fee_type: str = ""                  # 费用类型
    estimated_range_low: Decimal = Decimal("0.00")   # 保守下限
    estimated_range_high: Decimal = Decimal("0.00")  # 保守上限
    basis: str = ""                     # 估算依据
    methodology: str = ""               # 计算方法
    confidence: str = "medium"          # 高/中/低
    is_material: bool = False           # 是否重大
    audit_note: str = ""                # 审计说明


@dataclass
class FinancialTerms:
    """采购合同财务条款汇总"""
    contract_amount: Decimal = Decimal("0.00")      # 合同总价
    goods_amount: Decimal = Decimal("0.00")         # 货款
    transportation_fee: Decimal | None = None       # 运输费
    warehousing_cost: Decimal | None = None         # 仓储费
    insurance_fee: Decimal | None = None            # 保险费
    tax_amount: Decimal | None = None               # 税额
    tax_rate: Decimal | None = None                 # 税率
    other_fees: list[dict[str, Any]] = field(default_factory=list)  # 其他费用
    fee_basis: str = ""                             # 费用计算依据
    explicitly_stated: list[str] = field(default_factory=list)      # 已明确费用项
    estimates: list[FeeEstimate] = field(default_factory=list)      # 估算项


@dataclass
class TaxLiabilityClause:
    """重大税务责任条款"""
    is_critical: bool = False           # 是否属于重大税务责任条款
    responsible_party: str = ""         # 责任方
    tax_type: str = ""                  # 税种
    tax_rate: Decimal = Decimal("0.00") # 税率
    invoice_type: str = ""              # 发票类型
    trigger_event: str = ""             # 触发条件
    consequence: str = ""               # 责任后果
    full_text: str = ""                 # 原文
    risk_flag: str = ""                 # 风险标记


@dataclass
class ComplianceAssessment:
    """合同合规性评估"""
    score: int = 100                    # 合规得分 0-100
    risk_level: str = "low"             # 高/中/低
    missing_clauses: list[str] = field(default_factory=list)  # 缺失的重要条款
    risk_flags: list[str] = field(default_factory=list)       # 风险标记
    internal_control_notes: str = ""    # 内控初步评价


@dataclass
class AuditTrailItem:
    """审计溯源项"""
    field: str = ""                     # 字段
    source: str = ""                    # 来源：extracted / inferred / estimated
    basis: str = ""                     # 依据
    confidence: str = "high"            # 置信度


@dataclass
class ContractParseResult:
    """合同解析结果（完整版）"""
    # 合同基本信息
    contract_type: str = ""                     # 合同类型：销售/采购/服务/租赁等
    contract_valid: bool = True                 # 合同是否成立（CAS 14 第五条）
    effective_conditions: str = ""            # 生效条件
    commercial_substance: bool = True           # 是否具有商业实质
    collection_probable: bool = True            # 对价是否很可能收回
    
    # 合同主体
    parties: list[ContractParty] = field(default_factory=list)
    
    # 时间信息
    signing_date: str = ""                    # 签署日期
    period: ContractPeriod = field(default_factory=ContractPeriod)
    
    # 交易价格（CAS 14 第十四条至第十九条）
    price: ContractPrice = field(default_factory=ContractPrice)
    
    # 履约义务（CAS 14 第九条、第十条）
    performance_obligations: list[PerformanceObligation] = field(default_factory=list)
    
    # 违约责任（CAS 13）
    penalties: list[ContractPenalty] = field(default_factory=list)
    
    # 合同成本（CAS 14 第二十六条至第二十九条）
    contract_costs: list[ContractCost] = field(default_factory=list)
    
    # 金融资产（CAS 22）
    financial_assets: list[FinancialAssetInfo] = field(default_factory=list)
    
    # 税务处理
    tax_treatment: TaxTreatment = field(default_factory=TaxTreatment)
    
    # ============== 采购合同扩展字段 ==============
    commodities: list[CommodityItem] = field(default_factory=list)          # 商品明细
    financial_terms: FinancialTerms = field(default_factory=FinancialTerms) # 财务条款
    tax_liability: TaxLiabilityClause = field(default_factory=TaxLiabilityClause)  # 税务责任
    compliance_assessment: ComplianceAssessment = field(default_factory=ComplianceAssessment)  # 合规评估
    audit_trail: list[AuditTrailItem] = field(default_factory=list)         # 审计溯源链
    
    # 摘要和会计说明
    summary: str = ""                           # 合同摘要
    accounting_notes: str = ""                # 会计处理说明
    five_step_analysis: str = ""              # 五步法分析
    
    # 置信度
    confidence_score: Decimal = Decimal("0.00") # 置信度（0-1）
    raw_text: str = ""                        # 原始文本（用于人工复核）


class ContractParser:
    """
    合同解析器（基于 CAS 14 收入准则 + 采购合同合规审查）

    功能描述：使用 LLM 对合同文本进行结构化解析，提取会计关键信息
    业务逻辑：
        1. 构建合同解析 Prompt（包含 CAS 14 五步法、采购商品、财务、税务责任要求）
        2. 调用 LLM 进行语义理解和结构化提取
        3. 解析 LLM 返回的 JSON，转换为 ContractParseResult
        4. 进行会计校验与合规性校验

    会计口径：
        - 五步法：识别合同 → 识别履约义务 → 确定交易价格 → 分摊交易价格 → 确认收入
        - 价税分离：总价款 = 不含税金额 + 税额（符合增值税会计处理）
        - 履约义务：识别单项/多项履约义务，影响收入确认时点
        - 违约责任：评估是否需预提负债（预计负债）
        - 背靠背：付款时间安排，不影响交易价格，但影响信用风险
    """

    def __init__(self, llm_client: LightweightLLMClient | None = None):
        self.llm = llm_client or LightweightLLMClient()

    def _build_prompt(self, contract_text: str) -> list[dict[str, Any]]:
        """
        构建合同解析 Prompt（基于 CAS 14 五步法 + 采购合同扩展）

        功能描述：根据企业会计准则要求，构建结构化提取 Prompt
        业务逻辑：
            1. 定义输出 JSON Schema（包含五步法所有参数）
            2. 提供示例和约束条件
            3. 强调会计准则要求（收入确认、增值税、预计负债）
            4. 增加采购合同商品明细、财务条款、税务责任、合规评估要求
        """
        system_prompt = """你是一位专业的财务合同解析专家，精通中国会计准则（CAS 14 收入准则、CAS 13 或有事项、CAS 22 金融工具）及采购合同合规审查。

请从以下合同文本中提取关键信息，并以严格的 JSON 格式返回。

【第一步：识别合同（CAS 14 第五条）】
1. 合同主体：识别甲方、乙方、丙方（如有），包括名称、地址、税号、是否具备民事行为能力
2. 合同成立判断：是否满足5项条件（主体能力、权利义务明确、商业实质、对价很可能收回、生效条件）
3. 生效条件：签字盖章、预付款到账、其他条件
4. 合同期限与终止条款

【第二步：识别履约义务（CAS 14 第九条、第十条）】
1. 合同包含多少项承诺（交付物/服务）
2. 每项承诺是否可明确区分（客户能单独获益、承诺可单独识别）
3. 是否存在重大整合服务、高度关联修改、定制化改造
4. 若为单一整合服务，则整体作为一项履约义务

【第三步：确定交易价格（CAS 14 第十四条至第十九条）】
1. 固定对价金额（不含增值税）
2. 可变对价：奖励、罚款、折扣、绩效扣款等，需按期望值/最可能发生金额估计
   - 限制条件：满足"极可能不会重大转回"才能计入交易价格
3. 重大融资成分：付款周期超过1年的，需折现
4. 非现金对价：按公允价值计量
5. 应付客户对价：冲减交易价格
6. 价税分离：增值税为价外税，不计入交易价格
   - 含税总价、税率、税额、不含税金额
7. 背靠背条款：属于付款时间安排，不是可变对价，不调整交易价格
   - 影响：对价是否很可能收回的评估、预期信用损失

【第四步：分摊交易价格（CAS 14 第二十条至第二十四条）】
1. 各单项履约义务的单独售价
2. 按单独售价比例分摊交易价格
3. 合同折扣、可变对价的分摊规则

【第五步：确认收入（CAS 14 第十一条、第十二条）】
1. 履约模式判定：
   - 时段法三选一条件：
     a) 客户在履约同时取得并消耗经济利益
     b) 客户能控制在建中的商品
     c) 产出具有不可替代用途，且企业拥有合格收款权（就累计已完成部分有权收款）
   - 若不满足时段法，则按控制权转移的时点确认收入
2. 收入确认方法：时点法/时段法
3. 履约进度计量（如适用时段法）

【违约责任（CAS 13 或有事项）】
1. 违约条款原文摘录
2. 违约金金额或计算方式
3. 是否很可能发生违约
4. 如很可能发生，需预提的金额（预计负债）
5. 对收入确认的影响说明

【合同成本（CAS 14 第二十六条至第二十九条）】
1. 合同取得成本：佣金、投标费等
2. 合同履约成本：直接人工、直接材料、制造费用等
3. 摊销方法和期间

【金融资产（CAS 22）】
1. 应收账款/合同资产分类
2. 预期信用损失评估
3. 风险评级

【税务处理】
1. 增值税：税率、税额、价税分离
2. 所得税：收入确认时点对所得税的影响
3. 特殊处理：税负转嫁等

【采购合同商品明细专项】
1. 逐项提取商品/货物信息：产品名称、规格、型号、品牌、单位、数量、单价、小计
2. 对每项提取重量参数（如适用）、质量标准、交货条款、质保期
3. 计算数量×单价是否等于小计，记录不一致
4. 根据产品类型标记应当具备但缺失的属性（如设备缺型号、钢材缺重量）
5. 输出商品数组 commodities，每个元素包含 missing_attributes 和 consistency_errors

【采购合同财务条款专项】
1. 提取所有明确费用项目：货款、运输费、仓储费、保险费、税费、其他费用
2. 对未明确费用，基于行业惯例给出 conservative estimate 区间
3. 输出 financial_terms：
   - explicitly_stated: 已明确费用项名称列表
   - estimates: 未明确费用的估算数组，每项包含 fee_type、estimated_range_low、estimated_range_high、basis、methodology、confidence、is_material、audit_note

【重大税务责任条款专项】
1. 识别类似"Before Party A makes payment, Party B shall issue a 13% value-added tax special invoice..."的条款
2. 输出 tax_liability：is_critical、responsible_party、tax_type、tax_rate、invoice_type、trigger_event、consequence、full_text、risk_flag
3. 若存在以下情形标记 is_critical=true：
   - 约定因发票/账户问题导致付款失败由某方承担全部责任
   - 约定税率但缺少发票类型
   - 约定开票义务但未约定逾期开票违约责任
   - 税负转嫁条款与主合同价格条款不一致

【合规性评估专项】
1. 评估合同是否包含以下关键条款：主体信息完整、标的明确、质量标准、验收条款、付款条件、税务责任、违约责任、争议解决
2. 输出 compliance_assessment：score（0-100）、risk_level（high/medium/low）、missing_clauses、risk_flags、internal_control_notes
3. 缺失重要条款应扣分；重大税务责任风险应降级 risk_level

输出必须是合法的JSON，不要包含任何其他文字。"""

        user_prompt = f"""请解析以下合同文本：

---合同文本开始---
{contract_text[:8000]}  # 限制长度，避免超出 LLM 上下文
---合同文本结束---

请严格按照上述要求提取信息，返回JSON格式。"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _parse_llm_response(self, response: LLMResult) -> ContractParseResult:
        """
        解析 LLM 返回的 JSON

        功能描述：将 LLM 的 JSON 输出转换为 ContractParseResult 对象
        业务逻辑：
            1. 解析 JSON 字符串
            2. 提取各字段并转换为适当类型
            3. 进行金额计算和校验
            4. 设置置信度评分
        """
        result = ContractParseResult()

        if not response.available or not response.content:
            result.accounting_notes = f"LLM解析失败：{response.error}"
            return result

        try:
            data = json.loads(response.content)
        except json.JSONDecodeError:
            # 尝试从文本中提取 JSON
            json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    result.accounting_notes = "LLM返回格式错误，无法解析JSON"
                    return result
            else:
                result.accounting_notes = "LLM返回格式错误，未找到JSON"
                return result

        # 解析合同基本信息
        result.contract_type = data.get("contract_type", "")
        result.contract_valid = data.get("contract_valid", True)
        result.effective_conditions = data.get("effective_conditions", "")
        result.commercial_substance = data.get("commercial_substance", True)
        result.collection_probable = data.get("collection_probable", True)

        # 解析合同主体
        parties_data = data.get("parties", [])
        for party_data in parties_data:
            party = ContractParty(
                name=party_data.get("name", ""),
                role=party_data.get("role", ""),
                address=party_data.get("address", ""),
                contact=party_data.get("contact", ""),
                tax_id=party_data.get("tax_id", ""),
                legal_capacity=party_data.get("legal_capacity", True),
            )
            result.parties.append(party)

        # 解析签署日期
        result.signing_date = data.get("signing_date", "")

        # 解析执行周期
        period_data = data.get("period", {})
        result.period = ContractPeriod(
            start_date=period_data.get("start_date", ""),
            end_date=period_data.get("end_date", ""),
            duration_days=period_data.get("duration_days", 0),
            is_indefinite=period_data.get("is_indefinite", False),
            termination_terms=period_data.get("termination_terms", ""),
        )

        # 解析交易价格（进行价税分离计算）
        price_data = data.get("price", {})
        total_amount = self._parse_amount(price_data.get("total_amount", "0"))
        tax_rate = self._parse_tax_rate(price_data.get("tax_rate", "0"))

        # 计算税额和不含税金额
        tax_amount = (total_amount * tax_rate / (1 + tax_rate)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        amount_excl_tax = (total_amount - tax_amount).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)

        result.price = ContractPrice(
            total_amount=total_amount,
            amount_excl_tax=amount_excl_tax,
            tax_rate=tax_rate,
            tax_amount=tax_amount,
            currency=price_data.get("currency", "CNY"),
            variable_consideration=self._parse_amount(price_data.get("variable_consideration", "0")),
            variable_type=price_data.get("variable_type", ""),
            variable_constraint=price_data.get("variable_constraint", ""),
            significant_financing=price_data.get("significant_financing", False),
            discount_rate=self._parse_amount(price_data.get("discount_rate", "0")),
            non_cash_consideration=self._parse_amount(price_data.get("non_cash_consideration", "0")),
            payable_to_customer=self._parse_amount(price_data.get("payable_to_customer", "0")),
            payment_terms=price_data.get("payment_terms", ""),
            back_to_back=price_data.get("back_to_back", False),
            installment_schedule=price_data.get("installment_schedule", []),
        )

        # 解析履约义务
        obligations_data = data.get("performance_obligations", [])
        for idx, obligation_data in enumerate(obligations_data, 1):
            obligation = PerformanceObligation(
                item_no=idx,
                description=obligation_data.get("description", ""),
                quantity=self._parse_amount(obligation_data.get("quantity", "0")),
                unit=obligation_data.get("unit", ""),
                unit_price=self._parse_amount(obligation_data.get("unit_price", "0")),
                total_price=self._parse_amount(obligation_data.get("total_price", "0")),
                distinct=obligation_data.get("distinct", True),
                separately_identifiable=obligation_data.get("separately_identifiable", True),
                highly_interdependent=obligation_data.get("highly_interdependent", False),
                integration_service=obligation_data.get("integration_service", False),
                revenue_recognition_method=obligation_data.get("revenue_recognition_method", ""),
                time_method_criteria=obligation_data.get("time_method_criteria", []),
                qualified_payment_right=obligation_data.get("qualified_payment_right", False),
                irreplaceable_use=obligation_data.get("irreplaceable_use", False),
                standalone_selling_price=self._parse_amount(obligation_data.get("standalone_selling_price", "0")),
                allocation_ratio=self._parse_amount(obligation_data.get("allocation_ratio", "0")),
            )
            result.performance_obligations.append(obligation)

        # 解析违约责任
        penalties_data = data.get("penalties", [])
        for penalty_data in penalties_data:
            penalty = ContractPenalty(
                penalty_clause=penalty_data.get("penalty_clause", ""),
                penalty_amount=self._parse_amount(penalty_data.get("penalty_amount", "0")),
                penalty_type=penalty_data.get("penalty_type", ""),
                is_probable=penalty_data.get("is_probable", False),
                provision_required=penalty_data.get("provision_required", False),
                provision_amount=self._parse_amount(penalty_data.get("provision_amount", "0")),
                impact_on_revenue=penalty_data.get("impact_on_revenue", ""),
            )
            result.penalties.append(penalty)

        # 解析合同成本
        costs_data = data.get("contract_costs", [])
        for cost_data in costs_data:
            cost = ContractCost(
                cost_type=cost_data.get("cost_type", ""),
                amount=self._parse_amount(cost_data.get("amount", "0")),
                amortization_method=cost_data.get("amortization_method", ""),
                amortization_period=cost_data.get("amortization_period", ""),
            )
            result.contract_costs.append(cost)

        # 解析金融资产
        assets_data = data.get("financial_assets", [])
        for asset_data in assets_data:
            asset = FinancialAssetInfo(
                asset_type=asset_data.get("asset_type", ""),
                amount=self._parse_amount(asset_data.get("amount", "0")),
                expected_credit_loss=self._parse_amount(asset_data.get("expected_credit_loss", "0")),
                risk_rating=asset_data.get("risk_rating", ""),
            )
            result.financial_assets.append(asset)

        # 解析税务处理
        tax_data = data.get("tax_treatment", {})
        result.tax_treatment = TaxTreatment(
            tax_type=tax_data.get("tax_type", ""),
            tax_rate=self._parse_tax_rate(tax_data.get("tax_rate", "0")),
            tax_amount=self._parse_amount(tax_data.get("tax_amount", "0")),
            tax_basis=tax_data.get("tax_basis", ""),
            special_treatment=tax_data.get("special_treatment", ""),
        )

        # ============== 解析采购合同扩展字段 ==============
        result.commodities = self._parse_commodities(data.get("commodities", []))
        result.financial_terms = self._parse_financial_terms(data.get("financial_terms", {}))
        result.tax_liability = self._parse_tax_liability(data.get("tax_liability", {}))
        result.compliance_assessment = self._parse_compliance_assessment(data.get("compliance_assessment", {}))
        result.audit_trail = self._parse_audit_trail(data.get("audit_trail", []))

        # 解析摘要和会计说明
        result.summary = data.get("summary", "")
        result.accounting_notes = data.get("accounting_notes", "")
        result.five_step_analysis = data.get("five_step_analysis", "")

        # 设置置信度
        result.confidence_score = Decimal(str(data.get("confidence_score", "0")))

        return result

    def _parse_commodities(self, commodities_data: list[dict[str, Any]]) -> list[CommodityItem]:
        """解析商品明细数组"""
        commodities: list[CommodityItem] = []
        for idx, item_data in enumerate(commodities_data, 1):
            item = CommodityItem(
                item_no=item_data.get("item_no", idx),
                product_name=item_data.get("product_name", ""),
                specification=item_data.get("specification", ""),
                model_number=item_data.get("model_number", ""),
                brand=item_data.get("brand", ""),
                unit=item_data.get("unit", ""),
                quantity=self._parse_amount(item_data.get("quantity", "0")),
                unit_price=self._parse_amount(item_data.get("unit_price", "0")),
                total_price=self._parse_amount(item_data.get("total_price", "0")),
                weight=item_data.get("weight", ""),
                quality_standard=item_data.get("quality_standard", ""),
                delivery_terms=item_data.get("delivery_terms", ""),
                warranty_period=item_data.get("warranty_period", ""),
                missing_attributes=item_data.get("missing_attributes", []),
                consistency_errors=item_data.get("consistency_errors", []),
            )
            commodities.append(item)
        return commodities

    def _parse_financial_terms(self, financial_data: dict[str, Any]) -> FinancialTerms:
        """解析财务条款"""
        estimates = []
        for est_data in financial_data.get("estimates", []):
            estimates.append(
                FeeEstimate(
                    fee_type=est_data.get("fee_type", ""),
                    estimated_range_low=self._parse_amount(est_data.get("estimated_range_low", "0")),
                    estimated_range_high=self._parse_amount(est_data.get("estimated_range_high", "0")),
                    basis=est_data.get("basis", ""),
                    methodology=est_data.get("methodology", ""),
                    confidence=est_data.get("confidence", "medium"),
                    is_material=est_data.get("is_material", False),
                    audit_note=est_data.get("audit_note", ""),
                )
            )

        return FinancialTerms(
            contract_amount=self._parse_amount(financial_data.get("contract_amount", "0")),
            goods_amount=self._parse_amount(financial_data.get("goods_amount", "0")),
            transportation_fee=self._parse_optional_amount(financial_data.get("transportation_fee")),
            warehousing_cost=self._parse_optional_amount(financial_data.get("warehousing_cost")),
            insurance_fee=self._parse_optional_amount(financial_data.get("insurance_fee")),
            tax_amount=self._parse_optional_amount(financial_data.get("tax_amount")),
            tax_rate=self._parse_optional_tax_rate(financial_data.get("tax_rate")),
            other_fees=financial_data.get("other_fees", []),
            fee_basis=financial_data.get("fee_basis", ""),
            explicitly_stated=financial_data.get("explicitly_stated", []),
            estimates=estimates,
        )

    def _parse_tax_liability(self, tax_liability_data: dict[str, Any]) -> TaxLiabilityClause:
        """解析重大税务责任条款"""
        return TaxLiabilityClause(
            is_critical=tax_liability_data.get("is_critical", False),
            responsible_party=tax_liability_data.get("responsible_party", ""),
            tax_type=tax_liability_data.get("tax_type", ""),
            tax_rate=self._parse_tax_rate(tax_liability_data.get("tax_rate", "0")),
            invoice_type=tax_liability_data.get("invoice_type", ""),
            trigger_event=tax_liability_data.get("trigger_event", ""),
            consequence=tax_liability_data.get("consequence", ""),
            full_text=tax_liability_data.get("full_text", ""),
            risk_flag=tax_liability_data.get("risk_flag", ""),
        )

    def _parse_compliance_assessment(self, compliance_data: dict[str, Any]) -> ComplianceAssessment:
        """解析合规性评估"""
        return ComplianceAssessment(
            score=int(compliance_data.get("score", 100)),
            risk_level=compliance_data.get("risk_level", "low"),
            missing_clauses=compliance_data.get("missing_clauses", []),
            risk_flags=compliance_data.get("risk_flags", []),
            internal_control_notes=compliance_data.get("internal_control_notes", ""),
        )

    def _parse_audit_trail(self, audit_trail_data: list[dict[str, Any]]) -> list[AuditTrailItem]:
        """解析审计溯源链"""
        trail = []
        for item_data in audit_trail_data:
            trail.append(
                AuditTrailItem(
                    field=item_data.get("field", ""),
                    source=item_data.get("source", ""),
                    basis=item_data.get("basis", ""),
                    confidence=item_data.get("confidence", "high"),
                )
            )
        return trail

    def _parse_optional_amount(self, value: Any) -> Decimal | None:
        """解析可选金额，None 或空值返回 None"""
        if value is None or value == "":
            return None
        parsed = self._parse_amount(value)
        return parsed if parsed != Decimal("0.00") else None

    def _parse_optional_tax_rate(self, value: Any) -> Decimal | None:
        """解析可选税率，None 或空值返回 None"""
        if value is None or value == "":
            return None
        parsed = self._parse_tax_rate(value)
        return parsed if parsed != Decimal("0.00") else None

    def _parse_amount(self, value: Any) -> Decimal:
        """解析金额字符串为 Decimal"""
        if isinstance(value, (int, float)):
            return Decimal(str(value)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        if isinstance(value, str):
            # 移除货币符号和逗号
            cleaned = re.sub(r'[^\d.]', '', value)
            if cleaned:
                return Decimal(cleaned).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
        return Decimal("0.00")

    def _parse_tax_rate(self, value: Any) -> Decimal:
        """解析税率"""
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            # 处理 "13%" 或 "0.13" 格式
            cleaned = value.replace('%', '').strip()
            if cleaned:
                try:
                    rate = Decimal(cleaned)
                    if rate > 1:
                        rate = rate / 100  # 转换为小数
                    return rate
                except Exception:
                    return Decimal("0.00")
        return Decimal("0.00")

    def parse(self, contract_text: str) -> ContractParseResult:
        """
        解析合同文本

        功能描述：主入口函数，调用 LLM 解析合同并返回结构化结果
        业务逻辑：
            1. 构建 Prompt
            2. 调用 LLM
            3. 解析响应
            4. 保存原始文本用于人工复核

        Args:
            contract_text: 合同文本（已从 PDF 提取）

        Returns:
            ContractParseResult: 结构化合同解析结果
        """
        if not contract_text or len(contract_text.strip()) < 50:
            return ContractParseResult(
                accounting_notes="合同文本过短，无法解析",
                confidence_score=Decimal("0.00"),
            )

        messages = self._build_prompt(contract_text)
        response = self.llm.chat(messages, temperature=0.1)  # 低温度，提高确定性

        result = self._parse_llm_response(response)
        result.raw_text = contract_text[:2000]  # 保存前2000字符用于复核

        return result

    def validate_accounting(self, result: ContractParseResult) -> list[str]:
        """
        会计校验（基于 CAS 14 五步法）

        功能描述：对解析结果进行会计准则校验
        业务逻辑：
            1. 合同成立校验：是否满足5项条件
            2. 价税合计校验：总价 = 不含税金额 + 税额
            3. 履约义务校验：识别单项/多项履约义务
            4. 交易价格分摊校验：分摊比例之和是否为100%
            5. 违约责任校验：评估预计负债
            6. 背靠背条款校验：是否正确处理
            7. 采购合同商品勾稽校验

        Returns:
            list[str]: 校验结果列表（空表示通过）
        """
        errors = []

        # 1. 合同成立校验（CAS 14 第五条）
        if not result.contract_valid:
            errors.append("合同不满足成立条件，不能适用收入准则")
        if not result.commercial_substance:
            errors.append("合同不具有商业实质，不能确认收入")
        if not result.collection_probable:
            errors.append("对价不是很可能收回，收到款项应作为负债")

        # 2. 价税分离校验
        expected_total = result.price.amount_excl_tax + result.price.tax_amount
        if abs(expected_total - result.price.total_amount) > Decimal("0.01"):
            errors.append(
                f"价税分离校验失败：不含税金额({result.price.amount_excl_tax}) + "
                f"税额({result.price.tax_amount}) ≠ 总价({result.price.total_amount})"
            )

        # 3. 履约义务校验（CAS 14 第九条、第十条）
        if not result.performance_obligations:
            errors.append("未识别到履约义务，请人工复核")
        else:
            for obligation in result.performance_obligations:
                if not obligation.revenue_recognition_method:
                    errors.append(f"履约义务{obligation.item_no}未识别收入确认方法（时点/时段）")
                if obligation.revenue_recognition_method == "时段法" and not obligation.time_method_criteria:
                    errors.append(f"履约义务{obligation.item_no}适用时段法，但未说明满足哪项条件")

        # 4. 交易价格分摊校验（CAS 14 第二十条至第二十四条）
        if len(result.performance_obligations) > 1:
            total_ratio = sum(o.allocation_ratio for o in result.performance_obligations)
            if abs(total_ratio - Decimal("1.00")) > Decimal("0.01") and total_ratio > 0:
                errors.append(f"交易价格分摊比例之和不为100%：{total_ratio}")

        # 5. 违约责任校验（CAS 13）
        for penalty in result.penalties:
            if penalty.is_probable and not penalty.provision_required:
                errors.append(
                    f"违约责任很可能发生，但未预提：{penalty.penalty_clause[:50]}..."
                )

        # 6. 背靠背条款校验
        if result.price.back_to_back and result.collection_probable:
            errors.append("背靠背付款安排下，对价很可能收回的评估可能过于乐观")

        # 7. 可变对价校验（CAS 14 第十六条）
        if result.price.variable_consideration > 0 and not result.price.variable_constraint:
            errors.append("存在可变对价，但未说明限制条件（极可能不会重大转回）")

        # 8. 合同成本校验（CAS 14 第二十六条至第二十九条）
        for cost in result.contract_costs:
            if cost.cost_type == "取得成本" and cost.amount > result.price.amount_excl_tax * Decimal("0.05"):
                errors.append(f"合同取得成本({cost.amount})超过交易价格的5%，需检查是否符合资本化条件")

        # 9. 采购合同商品勾稽校验
        for commodity in result.commodities:
            expected_total = (commodity.quantity * commodity.unit_price).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
            if commodity.total_price > Decimal("0") and abs(expected_total - commodity.total_price) > Decimal("0.01"):
                errors.append(
                    f"商品{commodity.item_no}金额勾稽不一致："
                    f"数量({commodity.quantity}) × 单价({commodity.unit_price}) = {expected_total}，"
                    f"合同小计({commodity.total_price})"
                )

        # 10. 税务责任与一般税务条款一致性校验
        if (
            result.tax_liability.is_critical
            and result.tax_liability.tax_rate > 0
            and result.tax_treatment.tax_rate > 0
            and result.tax_liability.tax_rate != result.tax_treatment.tax_rate
        ):
            errors.append(
                f"重大税务责任条款税率({result.tax_liability.tax_rate})"
                f"与税务处理税率({result.tax_treatment.tax_rate})不一致"
            )

        return errors

    def to_dict(self, result: ContractParseResult) -> dict[str, Any]:
        """将解析结果转换为可序列化的字典"""
        return asdict(result)
