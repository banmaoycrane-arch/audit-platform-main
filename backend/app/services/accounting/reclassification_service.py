# -*- coding: utf-8 -*-
"""
模块功能：往来主科目与报表重分类规则服务
业务场景：用于判断应收/预收、应付/预付等往来余额的列报建议
政策依据：企业会计准则关于会计科目分类和资产负债列报的基本原则
输入数据：会计科目编码、往来余额金额，余额金额以本科目正常方向为正数
输出结果：主科目分类、余额方向、建议列报科目与业务原因
创建日期：2026-06-19
更新记录：
    2026-06-19  建立 Task 5 往来重分类最小规则
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any


MONEY_PRECISION = Decimal("0.00")

MAIN_ACCOUNT_CATEGORIES = {
    "1": {"category": "asset", "category_name": "资产类", "normal_balance_direction": "debit"},
    "2": {"category": "liability", "category_name": "负债类", "normal_balance_direction": "credit"},
    "3": {"category": "common", "category_name": "共同类", "normal_balance_direction": "debit_or_credit"},
    "4": {"category": "equity", "category_name": "所有者权益类", "normal_balance_direction": "credit"},
    "5": {"category": "cost", "category_name": "成本类", "normal_balance_direction": "debit"},
    "6": {"category": "profit", "category_name": "损益类", "normal_balance_direction": "debit_or_credit"},
}

ACCOUNT_NAMES = {
    "1122": "应收账款",
    "1123": "预付账款",
    "1221": "其他应收款",
    "2202": "应付账款",
    "2203": "预收账款",
    "2241": "其他应付款",
}

RECLASSIFICATION_RULES = {
    "1122": {
        "positive": ("1122", "应收账款", "应收账款为正数，表示客户尚欠企业款项，列报为应收。"),
        "negative": ("2203", "预收账款", "应收账款出现负数，实质为客户预付或企业多收，建议重分类为预收。"),
    },
    "2203": {
        "positive": ("2203", "预收账款", "预收账款为正数，表示企业尚需履约或交付，列报为预收。"),
        "negative": ("1122", "应收账款", "预收账款出现负数，实质为客户尚欠企业款项，建议重分类为应收。"),
    },
    "2202": {
        "positive": ("2202", "应付账款", "应付账款为正数，表示企业尚欠供应商款项，列报为应付。"),
        "negative": ("1123", "预付账款", "应付账款出现负数，实质为企业预付或多付款，建议重分类为预付。"),
    },
    "1123": {
        "positive": ("1123", "预付账款", "预付账款为正数，表示企业已预付供应商款项，列报为预付。"),
        "negative": ("2202", "应付账款", "预付账款出现负数，实质为企业尚欠供应商款项，建议重分类为应付。"),
    },
}

COUNTERPARTY_SEMANTIC_NOTE = "对方单位只表示交易对象语义，不绑定借方或贷方方向。"
ENTRY_TAG_SEMANTIC_NOTE = "往来列报判断应结合具体科目和 EntryTag，不能只按借贷方向判断。"

RECLASSIFICATION_STANDARD_NOTE = (
    "依据《企业会计准则第30号——财务报表列报》，资产和负债应当分别列示，不得相互抵销。"
    "当往来科目余额方向与其正常余额方向相反时，应按经济实质重分类列报，"
    "使资产负债表反映真实的债权、债务或预收/预付关系。"
)

RECLASSIFICATION_AUDIT_PROFILES: dict[tuple[str, str], dict[str, Any]] = {
    ("1122", "negative"): {
        "standard_basis": "CAS30 财务报表列报：应收类科目出现贷方余额，实质为预收客户款项，应列报为负债（预收账款）。",
        "standard_reference": "《企业会计准则第30号——财务报表列报》第九条、第二十条",
        "audit_assertion_risks": [
            {
                "assertion": "列报与披露",
                "risk_level": "high",
                "risk_description": "应收账款贷方余额未重分类将导致资产高估、负债低估，资产负债表分类不准确。",
            },
            {
                "assertion": "完整性",
                "risk_level": "medium",
                "risk_description": "预收款项可能未完整确认或仍挂在应收科目，影响合同负债/预收账款完整性。",
            },
            {
                "assertion": "计价与分摊",
                "risk_level": "medium",
                "risk_description": "坏账准备计提基础若仍按应收口径，可能导致减值计提不足或过度。",
            },
        ],
    },
    ("2203", "negative"): {
        "standard_basis": "CAS30 财务报表列报：预收账款出现借方余额，实质为客户欠款，应重分类为应收账款。",
        "standard_reference": "《企业会计准则第30号——财务报表列报》第九条、第二十条",
        "audit_assertion_risks": [
            {
                "assertion": "列报与披露",
                "risk_level": "high",
                "risk_description": "预收借方余额未重分类将低估应收账款、高估负债抵减效果，列报失真。",
            },
            {
                "assertion": "存在",
                "risk_level": "medium",
                "risk_description": "可能存在已发货未收款或结算串户，真实债权未在应收项目反映。",
            },
            {
                "assertion": "权利与义务",
                "risk_level": "medium",
                "risk_description": "合同履约义务与收款权利划分不清，影响收入确认时点判断。",
            },
        ],
    },
    ("2202", "negative"): {
        "standard_basis": "CAS30 财务报表列报：应付账款出现借方余额，实质为预付供应商款项，应列报为资产（预付账款）。",
        "standard_reference": "《企业会计准则第30号——财务报表列报》第九条、第二十条",
        "audit_assertion_risks": [
            {
                "assertion": "列报与披露",
                "risk_level": "high",
                "risk_description": "应付借方余额未重分类将导致负债低估、预付资产未单独列示。",
            },
            {
                "assertion": "存在",
                "risk_level": "medium",
                "risk_description": "可能存在重复付款、未核销预付或供应商退款未及时处理。",
            },
            {
                "assertion": "计价与分摊",
                "risk_level": "medium",
                "risk_description": "预付账龄较长未减值测试，可能影响资产可收回金额认定。",
            },
        ],
    },
    ("1123", "negative"): {
        "standard_basis": "CAS30 财务报表列报：预付账款出现贷方余额，实质为应付供应商款项，应列报为负债（应付账款）。",
        "standard_reference": "《企业会计准则第30号——财务报表列报》第九条、第二十条",
        "audit_assertion_risks": [
            {
                "assertion": "列报与披露",
                "risk_level": "high",
                "risk_description": "预付贷方余额未重分类将高估资产、低估应付，影响偿债能力判断。",
            },
            {
                "assertion": "完整性",
                "risk_level": "medium",
                "risk_description": "已到票未付款或暂估应付可能未完整计入应付账款。",
            },
            {
                "assertion": "权利与义务",
                "risk_level": "medium",
                "risk_description": "采购结算与发票勾稽不清，影响付款义务认定。",
            },
        ],
    },
}


def get_reclassification_audit_profile(main_account_code: str, balance_direction: str) -> dict[str, Any] | None:
    if balance_direction not in {"positive", "negative"}:
        return None
    return RECLASSIFICATION_AUDIT_PROFILES.get((main_account_code, balance_direction))


def build_reclassification_summary(adjustments: list[dict[str, Any]]) -> dict[str, Any]:
    """汇总重分类调整的准则说明与认定层面风险。"""
    if not adjustments:
        return {
            "applied": False,
            "adjustment_count": 0,
            "standard_note": RECLASSIFICATION_STANDARD_NOTE,
            "items": [],
            "assertion_risk_summary": [],
        }

    assertion_map: dict[str, dict[str, Any]] = {}
    items: list[dict[str, Any]] = []
    for adj in adjustments:
        profile = get_reclassification_audit_profile(
            adj.get("from_account_code", "")[:4],
            adj.get("balance_direction", ""),
        )
        risks = profile.get("audit_assertion_risks", []) if profile else []
        for risk in risks:
            key = f"{risk['assertion']}|{risk['risk_level']}"
            bucket = assertion_map.setdefault(
                key,
                {
                    "assertion": risk["assertion"],
                    "risk_level": risk["risk_level"],
                    "risk_description": risk["risk_description"],
                    "related_accounts": set(),
                },
            )
            bucket["related_accounts"].add(adj.get("from_account_code", ""))

        items.append(
            {
                "from_account_code": adj.get("from_account_code"),
                "from_account_name": adj.get("from_account_name"),
                "to_account_code": adj.get("to_account_code"),
                "to_account_name": adj.get("to_account_name"),
                "amount": adj.get("amount"),
                "reason": adj.get("reason"),
                "standard_basis": profile.get("standard_basis") if profile else None,
                "standard_reference": profile.get("standard_reference") if profile else None,
                "audit_assertion_risks": risks,
            }
        )

    assertion_risk_summary = [
        {
            "assertion": value["assertion"],
            "risk_level": value["risk_level"],
            "risk_description": value["risk_description"],
            "related_accounts": sorted(value["related_accounts"]),
        }
        for value in assertion_map.values()
    ]
    assertion_risk_summary.sort(
        key=lambda item: ({"high": 0, "medium": 1, "low": 2}.get(item["risk_level"], 3), item["assertion"])
    )

    return {
        "applied": True,
        "adjustment_count": len(adjustments),
        "standard_note": RECLASSIFICATION_STANDARD_NOTE,
        "items": items,
        "assertion_risk_summary": assertion_risk_summary,
    }


def _normalize_main_account_code(account_code: str) -> str:
    """
    功能描述：取得用于主科目规则判断的一级科目编码
    业务逻辑：明细科目或辅助核算编码仍归属于前四位主科目
    会计口径：主科目只承担国家会计准则定义的主分类

    Args:
        account_code: 会计科目编码，例如 1122、1122.01、112201

    Returns:
        str: 前四位主科目编码

    注意事项：
        1. 本函数不判断客户或供应商身份，交易对象语义由 EntryTag 承担。
    """
    clean_code = str(account_code).strip().replace(".", "")
    return clean_code[:4]


def _to_decimal(balance_amount: Decimal | int | float | str) -> Decimal:
    """
    功能描述：将余额金额统一转换为 Decimal 金额
    业务逻辑：金额计算不使用 float 的二进制精度，统一保留两位小数
    会计口径：往来余额按元保留两位小数

    Args:
        balance_amount: 往来余额金额，以本科目正常方向为正数

    Returns:
        Decimal: 保留两位小数的余额金额

    注意事项：
        1. 外部传入 float 时先转为字符串，避免继续扩大浮点误差。
    """
    return Decimal(str(balance_amount)).quantize(MONEY_PRECISION, rounding=ROUND_HALF_UP)


def get_main_account_category(account_code: str) -> dict[str, str]:
    """
    功能描述：返回主科目的准则主分类
    业务逻辑：按科目编码首位判断资产、负债、共同、权益、成本、损益等主分类
    会计口径：主科目只承担国家会计准则定义的主分类，不表达交易对象借贷身份

    Args:
        account_code: 会计科目编码，例如 1122、2202

    Returns:
        dict[str, str]: 主科目编码、分类、正常余额方向和说明

    注意事项：
        1. 对方单位是交易对象语义，不随借方或贷方发生额改变。
    """
    main_account_code = _normalize_main_account_code(account_code)
    category_rule = MAIN_ACCOUNT_CATEGORIES.get(main_account_code[:1])
    if not category_rule:
        raise ValueError("无法识别主科目分类：请检查会计科目编码")

    return {
        "main_account_code": main_account_code,
        "main_account_name": ACCOUNT_NAMES.get(main_account_code, "未配置科目名称"),
        "category": category_rule["category"],
        "category_name": category_rule["category_name"],
        "normal_balance_direction": category_rule["normal_balance_direction"],
        "role_note": "主科目只承担国家会计准则定义的主分类，不承担对方单位借贷身份判断。",
        "counterparty_semantic_note": COUNTERPARTY_SEMANTIC_NOTE,
    }


def classify_counterparty_balance(
    account_code: str,
    balance_amount: Decimal | int | float | str,
) -> dict[str, Any]:
    """
    功能描述：判断往来余额正负方向并给出重分类列报建议
    业务逻辑：应收/预收、应付/预付按余额正负判断最终列报定性
    会计口径：余额金额以当前科目的正常方向为正数；负数表示反方向余额

    Args:
        account_code: 往来科目编码，例如 1122、2203、2202、1123
        balance_amount: 往来余额金额，正数为本科目正常方向余额，负数为反方向余额

    Returns:
        dict[str, Any]: 原科目、余额方向、建议列报科目、原因和语义说明

    注意事项：
        1. 本函数只提供列报建议，不直接改写凭证或资产负债表。
        2. 实务中还应结合客户/供应商等 EntryTag 做明细级判断。
    """
    main_account_code = _normalize_main_account_code(account_code)
    amount = _to_decimal(balance_amount)
    account_category = get_main_account_category(main_account_code)
    original_account_name = account_category["main_account_name"]

    if amount > 0:
        balance_direction = "positive"
    elif amount < 0:
        balance_direction = "negative"
    else:
        balance_direction = "zero"

    if balance_direction == "zero":
        presentation_account_code = main_account_code
        presentation_account_name = original_account_name
        reason = "往来余额为零，无需进行应收/预收或应付/预付重分类。"
    else:
        rule = RECLASSIFICATION_RULES.get(main_account_code, {})
        presentation_rule = rule.get(balance_direction)
        if presentation_rule:
            presentation_account_code, presentation_account_name, reason = presentation_rule
        else:
            presentation_account_code = main_account_code
            presentation_account_name = original_account_name
            reason = "该科目暂未配置往来重分类规则，保持原科目列报。"

    audit_profile = get_reclassification_audit_profile(main_account_code, balance_direction)
    reclassified = (
        balance_direction != "zero"
        and presentation_account_code != main_account_code
    )

    return {
        "original_account_code": main_account_code,
        "original_account_name": original_account_name,
        "main_account_category": account_category["category"],
        "main_account_category_name": account_category["category_name"],
        "balance_amount": amount,
        "balance_direction": balance_direction,
        "presentation_account_code": presentation_account_code,
        "presentation_account_name": presentation_account_name,
        "reason": reason,
        "reclassified": reclassified,
        "standard_basis": audit_profile.get("standard_basis") if audit_profile else None,
        "standard_reference": audit_profile.get("standard_reference") if audit_profile else None,
        "audit_assertion_risks": audit_profile.get("audit_assertion_risks", []) if audit_profile else [],
        "counterparty_semantic_note": COUNTERPARTY_SEMANTIC_NOTE,
        "entry_tag_semantic_note": ENTRY_TAG_SEMANTIC_NOTE,
    }
