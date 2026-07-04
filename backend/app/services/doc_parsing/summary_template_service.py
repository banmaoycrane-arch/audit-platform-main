"""
智能摘要模板库服务

与凭证字联动的摘要模板，包含科目模式、期望流向、风险模式
核心设计：摘要库不仅是推荐工具，更是审计案例库
"""

from dataclasses import dataclass
from typing import Any

# 摘要模板库（与凭证字联动）
SUMMARY_TEMPLATES: dict[str, dict[str, dict[str, Any]]] = {
    "银": {
        # 收款类
        "收款_销售收入": {
            "template": "收到{客户}货款",
            "voucher_type": "银",
            "debit_patterns": ["银行存款", "货币资金"],
            "credit_patterns": ["主营业务收入", "其他业务收入", "应交税费", "销项税额"],
            "expected_flow": "银行↑ → 收入↑",
            "keywords": ["收到", "货款", "销售款", "货款"],
            "business_meaning": "销售商品或提供劳务收取的款项",
            "risk_patterns": {
                "mismatch_credit": "贷方不是收入类科目，可能是款项性质确认错误",
            },
        },
        "收款_预收款": {
            "template": "收到{客户}预付款",
            "voucher_type": "银",
            "debit_patterns": ["银行存款", "货币资金"],
            "credit_patterns": ["预收账款", "合同负债"],
            "expected_flow": "银行↑ → 负债↑",
            "keywords": ["预收", "订金", "定金", "预付款"],
            "business_meaning": "预收客户款项，尚未提供商品或劳务",
        },
        "收款_往来款": {
            "template": "收到{单位}往来款",
            "voucher_type": "银",
            "debit_patterns": ["银行存款", "货币资金"],
            "credit_patterns": ["其他应付款", "其他应收款"],
            "expected_flow": "银行↑ → 往来↑",
            "keywords": ["往来", "还款", "退回"],
            "business_meaning": "往来款项收付",
        },
        "收款_借款": {
            "template": "收到{借款人}还款",
            "voucher_type": "银",
            "debit_patterns": ["银行存款", "货币资金"],
            "credit_patterns": ["短期借款", "长期借款", "其他应收款"],
            "expected_flow": "银行↑ → 借款↓",
            "keywords": ["还款", "还借款", "还款"],
            "business_meaning": "收回借款本金",
        },
        # 付款类
        "付款_采购款": {
            "template": "支付{供应商}{商品}款",
            "voucher_type": "银",
            "debit_patterns": ["在途物资", "原材料", "库存商品", "应付账款", "预付账款"],
            "credit_patterns": ["银行存款", "货币资金"],
            "expected_flow": "资产↑/负债↑ → 银行↓",
            "keywords": ["支付", "采购", "货款", "购货"],
            "business_meaning": "采购商品或材料支付的款项",
            "risk_patterns": {
                "mismatch_debit": "借方不是资产/应付类科目，可能是费用化错误",
            },
        },
        "付款_费用": {
            "template": "支付{费用项}",
            "voucher_type": "银",
            "debit_patterns": ["管理费用", "销售费用", "财务费用"],
            "credit_patterns": ["银行存款", "货币资金"],
            "expected_flow": "费用↑ → 银行↓",
            "keywords": ["支付", "费用", "手续费", "佣金"],
            "business_meaning": "支付期间费用",
        },
        "付款_工资": {
            "template": "发放{人员}工资",
            "voucher_type": "银",
            "debit_patterns": ["应付职工薪酬"],
            "credit_patterns": ["银行存款", "货币资金"],
            "expected_flow": "负债↓ → 银行↓",
            "keywords": ["工资", "薪金", "薪酬", "奖金"],
            "business_meaning": "发放职工工资薪酬",
        },
        "付款_税费": {
            "template": "缴纳税费",
            "voucher_type": "银",
            "debit_patterns": ["应交税费", "税金及附加"],
            "credit_patterns": ["银行存款", "货币资金"],
            "expected_flow": "负债↓/费用↑ → 银行↓",
            "keywords": ["税金", "税费", "缴税", "纳税"],
            "business_meaning": "缴纳税金",
        },
        "付款_借款": {
            "template": "偿还{借款人}借款",
            "voucher_type": "银",
            "debit_patterns": ["短期借款", "长期借款"],
            "credit_patterns": ["银行存款", "货币资金"],
            "expected_flow": "借款↓ → 银行↓",
            "keywords": ["还款", "还借款", "偿还"],
            "business_meaning": "偿还借款本金",
        },
    },
    "现": {
        "提现": {
            "template": "提现",
            "voucher_type": "现",
            "debit_patterns": ["库存现金"],
            "credit_patterns": ["银行存款", "货币资金"],
            "expected_flow": "现金↑ → 银行↓",
            "keywords": ["提现", "提取现金"],
            "business_meaning": "从银行提取现金",
        },
        "存现": {
            "template": "存现",
            "voucher_type": "现",
            "debit_patterns": ["银行存款", "货币资金"],
            "credit_patterns": ["库存现金"],
            "expected_flow": "银行↑ → 现金↓",
            "keywords": ["存现", "存入现金", "现金存款"],
            "business_meaning": "将现金存入银行",
        },
        "报销": {
            "template": "报销{部门}{人员}差旅费",
            "voucher_type": "现",
            "debit_patterns": ["管理费用", "销售费用", "差旅费"],
            "credit_patterns": ["库存现金", "其他应收款"],
            "expected_flow": "费用↑ → 现金↓/应收↓",
            "keywords": ["报销", "差旅费", "差旅"],
            "business_meaning": "报销员工差旅费",
        },
        "工资": {
            "template": "发放{人员}工资",
            "voucher_type": "现",
            "debit_patterns": ["应付职工薪酬"],
            "credit_patterns": ["库存现金"],
            "expected_flow": "负债↓ → 现金↓",
            "keywords": ["工资", "薪金", "薪酬"],
            "business_meaning": "以现金发放工资",
        },
        "备用金": {
            "template": "借出备用金",
            "voucher_type": "现",
            "debit_patterns": ["其他应收款"],
            "credit_patterns": ["库存现金"],
            "expected_flow": "应收↑ → 现金↓",
            "keywords": ["备用金", "借款", "预支"],
            "business_meaning": "借出备用金",
        },
    },
    "转": {
        "计提_工资": {
            "template": "计提{期间}工资",
            "voucher_type": "转",
            "debit_patterns": ["管理费用", "销售费用", "生产成本", "制造费用"],
            "credit_patterns": ["应付职工薪酬"],
            "expected_flow": "费用↑ → 负债↑",
            "keywords": ["计提", "工资", "薪酬", "人工"],
            "business_meaning": "期末计提应付职工薪酬",
        },
        "计提_折旧": {
            "template": "计提{期间}折旧",
            "voucher_type": "转",
            "debit_patterns": ["管理费用", "销售费用", "制造费用", "生产成本"],
            "credit_patterns": ["累计折旧"],
            "expected_flow": "费用↑ → 资产备抵↑",
            "keywords": ["计提", "折旧", "折旧费"],
            "business_meaning": "期末计提固定资产折旧",
        },
        "计提_税费": {
            "template": "计提{期间}税费",
            "voucher_type": "转",
            "debit_patterns": ["税金及附加", "管理费用"],
            "credit_patterns": ["应交税费"],
            "expected_flow": "费用↑ → 负债↑",
            "keywords": ["计提", "税金", "税费", "附加"],
            "business_meaning": "期末计提应交税金及附加",
        },
        "摊销_费用": {
            "template": "摊销{期间}{费用项}",
            "voucher_type": "转",
            "debit_patterns": ["管理费用", "销售费用"],
            "credit_patterns": ["长期待摊费用", "无形资产累计摊销", "预付账款"],
            "expected_flow": "费用↑ → 资产↓",
            "keywords": ["摊销", "待摊", "无形资产摊销"],
            "business_meaning": "摊销已支付的费用或无形资产",
        },
        "结转_成本": {
            "template": "结转{期间}销售成本",
            "voucher_type": "转",
            "debit_patterns": ["主营业务成本"],
            "credit_patterns": ["库存商品", "原材料"],
            "expected_flow": "成本↑ → 资产↓",
            "keywords": ["结转", "成本", "销售成本"],
            "business_meaning": "结转已销商品成本",
        },
        "结转_收入": {
            "template": "结转{期间}收入至本年利润",
            "voucher_type": "转",
            "debit_patterns": ["主营业务收入", "其他业务收入"],
            "credit_patterns": ["本年利润"],
            "expected_flow": "收入↓ → 权益↑",
            "keywords": ["结转", "收入", "本年利润"],
            "business_meaning": "期末结转各项收入到本年利润",
        },
        "结转_费用": {
            "template": "结转{期间}费用至本年利润",
            "voucher_type": "转",
            "debit_patterns": ["本年利润"],
            "credit_patterns": ["管理费用", "销售费用", "财务费用", "主营业务成本"],
            "expected_flow": "权益↓ → 费用↓",
            "keywords": ["结转", "费用", "本年利润"],
            "business_meaning": "期末结转各项费用到本年利润",
        },
        "坏账准备": {
            "template": "计提坏账准备",
            "voucher_type": "转",
            "debit_patterns": ["信用减值损失", "资产减值损失"],
            "credit_patterns": ["坏账准备", "应收账款坏账准备"],
            "expected_flow": "损失↑ → 准备↑",
            "keywords": ["坏账", "减值", "准备"],
            "business_meaning": "计提应收账款坏账准备",
        },
    },
    "记": {
        "调整_一般": {
            "template": "调整{科目}{说明}",
            "voucher_type": "记",
            "debit_patterns": ["任意"],
            "credit_patterns": ["任意"],
            "expected_flow": "调整分录",
            "keywords": ["调整", "更正", "补记"],
            "business_meaning": "一般调整分录",
            "risk_patterns": {
                "suspicious_amount": "调整金额占总金额比例过大",
                "suspicious_frequency": "短期内调整频繁",
            },
        },
        "内部调拨": {
            "template": "内部调拨{科目}",
            "voucher_type": "记",
            "debit_patterns": ["任意"],
            "credit_patterns": ["任意"],
            "expected_flow": "内部调拨",
            "keywords": ["调拨", "内部", "转移"],
            "business_meaning": "内部资产或往来调拨",
        },
        "更正_错账": {
            "template": "更正{原凭证}错账",
            "voucher_type": "记",
            "debit_patterns": ["任意"],
            "credit_patterns": ["任意"],
            "expected_flow": "错账更正",
            "keywords": ["更正", "错账", "红字"],
            "business_meaning": "更正前期差错",
            "risk_patterns": {
                "suspicious_late": "更正距原凭证时间过长",
            },
        },
    },
}


# 预定义风险案例库（用于向量检索和风险识别）
RISK_CASES: list[dict[str, Any]] = [
    {
        "id": "RC001",
        "summary_pattern": "收到货款",
        "debit_pattern": "银行存款",
        "credit_pattern": "应付账款",
        "risk_type": "错账",
        "risk_description": "摘要为收到货款，但贷方为应付账款而非收入类科目",
        "correct_pattern": "贷方应为：主营业务收入、应交税费等",
        "severity": "高",
        "audit_suggestion": "核实是否为销售退回或款项性质确认错误",
    },
    {
        "id": "RC002",
        "summary_pattern": "支付货款",
        "debit_pattern": "管理费用",
        "credit_pattern": "银行存款",
        "risk_type": "可疑",
        "risk_description": "摘要为支付货款，但借方为费用类科目",
        "correct_pattern": "借方应为：在途物资、原材料、库存商品、应付账款等",
        "severity": "中",
        "audit_suggestion": "核实款项性质，是否存在费用化错误",
    },
    {
        "id": "RC003",
        "summary_pattern": "收到货款",
        "debit_pattern": "银行存款",
        "credit_pattern": "其他应收款",
        "risk_type": "可疑",
        "risk_description": "摘要为收到货款，但贷方为其他应收款",
        "correct_pattern": "贷方应为：主营业务收入、预收账款等",
        "severity": "中",
        "audit_suggestion": "核实款项性质是否正确",
    },
    {
        "id": "RC004",
        "summary_pattern": "支付费用",
        "debit_pattern": "应收账款",
        "credit_pattern": "银行存款",
        "risk_type": "可疑",
        "risk_description": "摘要为支付费用，但借方为应收账款",
        "correct_pattern": "借方应为：管理费用、销售费用等",
        "severity": "中",
        "audit_suggestion": "核实是否为预付款项而非费用",
    },
    {
        "id": "RC005",
        "summary_pattern": "计提折旧",
        "debit_pattern": "银行存款",
        "credit_pattern": "累计折旧",
        "risk_type": "错账",
        "risk_description": "计提折旧但借方为银行存款",
        "correct_pattern": "借方应为：管理费用、销售费用、制造费用等",
        "severity": "高",
        "audit_suggestion": "折旧计提科目错误，需更正",
    },
    {
        "id": "RC006",
        "summary_pattern": "计提工资",
        "debit_pattern": "应付职工薪酬",
        "credit_pattern": "银行存款",
        "risk_type": "错账",
        "risk_description": "计提工资但借贷方向错误",
        "correct_pattern": "借方应为：管理费用、销售费用等；贷方应为：应付职工薪酬",
        "severity": "高",
        "audit_suggestion": "工资计提分录借贷方向错误",
    },
    {
        "id": "RC007",
        "summary_pattern": "结转成本",
        "debit_pattern": "库存商品",
        "credit_pattern": "主营业务成本",
        "risk_type": "错账",
        "risk_description": "结转成本但借贷方向错误",
        "correct_pattern": "借方应为：主营业务成本；贷方应为：库存商品",
        "severity": "高",
        "audit_suggestion": "成本结转借贷方向错误",
    },
    {
        "id": "RC008",
        "summary_pattern": "报销",
        "debit_pattern": "银行存款",
        "credit_pattern": "库存现金",
        "risk_type": "可疑",
        "risk_description": "报销但贷方为现金",
        "correct_pattern": "贷方应为：库存现金、其他应收款等",
        "severity": "低",
        "audit_suggestion": "核实报销支付方式是否符合公司规定",
    },
]


def get_templates_by_voucher_type(voucher_type: str) -> dict[str, dict[str, Any]]:
    """获取指定凭证字的所有模板"""
    return SUMMARY_TEMPLATES.get(voucher_type, {})


def match_template(summary: str, debit_account: str, credit_account: str) -> list[dict[str, Any]]:
    """
    匹配摘要模板

    Returns:
        匹配到的模板列表，按置信度排序
    """
    summary_lower = summary.lower()
    debit_lower = debit_account.lower()
    credit_lower = credit_account.lower()
    combined = f"{summary_lower} {debit_lower} {credit_lower}"

    matches: list[dict[str, Any]] = []

    for voucher_type, templates in SUMMARY_TEMPLATES.items():
        for name, template in templates.items():
            score = 0
            matched_keywords = []

            # 检查关键词匹配
            for kw in template.get("keywords", []):
                if kw.lower() in summary_lower:
                    score += 1
                    matched_keywords.append(kw)

            # 检查借方科目匹配
            debit_match = False
            for pattern in template.get("debit_patterns", []):
                if pattern.lower() in debit_lower or pattern.lower() in credit_lower:
                    debit_match = True
                    score += 2
                    break

            # 检查贷方科目匹配
            credit_match = False
            for pattern in template.get("credit_patterns", []):
                if pattern.lower() in debit_lower or pattern.lower() in credit_lower:
                    credit_match = True
                    score += 2
                    break

            if score > 0:
                matches.append({
                    "name": name,
                    "template": template["template"],
                    "voucher_type": voucher_type,
                    "expected_flow": template.get("expected_flow", ""),
                    "score": score,
                    "confidence": min(score / 5.0, 1.0),
                    "matched_keywords": matched_keywords,
                    "debit_match": debit_match,
                    "credit_match": credit_match,
                })

    # 按置信度排序
    matches.sort(key=lambda x: x["confidence"], reverse=True)
    return matches


def recommend_summary(voucher_type: str, debit_account: str, credit_account: str, amount: float) -> list[dict[str, Any]]:
    """
    推荐摘要

    基于凭证字和科目推荐摘要候选
    """
    templates = get_templates_by_voucher_type(voucher_type)
    candidates = []

    debit_lower = debit_account.lower()
    credit_lower = credit_account.lower()

    for name, template in templates.items():
        # 检查借方科目匹配
        debit_match = any(
            pattern.lower() in debit_lower or pattern.lower() in credit_lower
            for pattern in template.get("debit_patterns", [])
            if pattern != "任意"
        )

        # 检查贷方科目匹配
        credit_match = any(
            pattern.lower() in debit_lower or pattern.lower() in credit_lower
            for pattern in template.get("credit_patterns", [])
            if pattern != "任意"
        )

        if debit_match or credit_match:
            confidence = 0.9 if (debit_match and credit_match) else 0.6

            # 大额调整风险提示
            if amount > 1000000 and template.get("risk_patterns"):
                confidence *= 0.8

            candidates.append({
                "template": template["template"],
                "category": name,
                "voucher_type": voucher_type,
                "expected_flow": template.get("expected_flow", ""),
                "confidence": confidence,
                "business_meaning": template.get("business_meaning", ""),
            })

    return sorted(candidates, key=lambda x: x["confidence"], reverse=True)


def get_risk_cases() -> list[dict[str, Any]]:
    """获取所有风险案例"""
    return RISK_CASES


def match_risk_case(summary: str, debit_account: str, credit_account: str) -> list[dict[str, Any]]:
    """
    匹配风险案例

    检查当前分录是否符合预定义的风险模式
    """
    summary_lower = summary.lower()
    debit_lower = debit_account.lower()
    credit_lower = credit_account.lower()

    matched: list[dict[str, Any]] = []

    for case in RISK_CASES:
        # 检查摘要模式
        if case["summary_pattern"].lower() not in summary_lower:
            continue

        # 检查借方科目模式
        debit_match = case["debit_pattern"].lower() in debit_lower

        # 检查贷方科目模式
        credit_match = case["credit_pattern"].lower() in credit_lower

        if debit_match and credit_match:
            matched.append(case)

    return matched
