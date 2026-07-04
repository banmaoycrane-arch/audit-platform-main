# -*- coding: utf-8 -*-
"""
智能标签规则引擎（Entry Tag Rules Engine）。

业务场景：
    在凭证录入或导入时，根据分录的摘要、科目、金额、往来单位等信息，
    自动为会计分录分配预设的业务标签（TagCategory + EntryTag）。

政策依据：
    项目采用"一级科目 + Dimension"核心模型，标签仅用于辅助核算与语义分析，
    不参与借贷平衡校验。自动标签可作为 AI 建议或规则标签，需经规则控制。

输入数据：
    - ledger_id: 账簿 ID
    - entry 或 VoucherEntryLine 的分录信息（account_code, account_name, summary,
      debit_amount, credit_amount, counterparty, counterparty_id 等）

输出结果：
    - 标签建议列表，每项包含 category_code, tag_value, weight, confidence, tag_source

规则优先级：
    1. 往来单位规则：counterparty 非空 → counterparty 标签
    2. 科目分类规则：根据 account_code 前缀识别资产/负债/权益/成本/损益
    3. 业务类型规则：根据摘要关键词识别销售、采购、费用、投资等
    4. 金额规模规则：根据金额大小识别大额/特大额
    5. 项目/部门规则：根据摘要中的项目名、部门名识别
"""
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.services.doc_parsing.tag_category_service import get_or_create_category


@dataclass
class TagSuggestion:
    """标签建议对象。"""

    category_code: str
    tag_value: str
    display_name: str
    weight: float
    confidence: float
    tag_source: str = "rule"
    value_id: int | None = None


# 科目分类映射规则（一级科目前缀）
ACCOUNT_CATEGORY_RULES = {
    "1": ("asset", "资产类"),
    "2": ("liability", "负债类"),
    "3": ("equity", "权益类"),
    "4": ("cost", "成本类"),
    "5": ("profit_loss", "损益类"),
    "6": ("profit_loss", "损益类"),
}

# 业务类型关键词规则
BUSINESS_TYPE_KEYWORDS = {
    "销售收入": ["销售", "售", "收入", "货款", "销货"],
    "采购支出": ["采购", "购货", "进货", "货款", "材料"],
    "管理费用": ["办公费", "差旅费", "招待费", "会议费", "咨询费", "审计费"],
    "工资薪酬": ["工资", "薪金", "奖金", "福利", "社保", "公积金"],
    "税费": ["增值税", "所得税", "税金", "附加税", "印花税"],
    "银行收付": ["转账", "汇款", "银行", "存款", "取现"],
    "投资": ["投资", "股权", "股票", "基金"],
    "借款": ["借款", "贷款", "融资", "还款"],
    "固定资产": ["购置", "设备", "车辆", "房产", "折旧"],
}

# 金额规模规则（单位：元）
AMOUNT_SCALE_RULES = [
    (10_000_000, "千万级"),
    (1_000_000, "百万级"),
    (100_000, "十万级"),
    (10_000, "万元级"),
]

# 项目识别关键词前缀
PROJECT_PREFIXES = ["项目", "project", "工程"]
DEPARTMENT_KEYWORDS = ["部", "中心", "审计一部", "审计二部", "财务部"]


def _extract_amount(entry: dict[str, Any]) -> Decimal:
    """
    提取分录金额（借方或贷方中较大者）。
    """
    debit = Decimal(str(entry.get("debit_amount") or 0))
    credit = Decimal(str(entry.get("credit_amount") or 0))
    return max(debit, credit)


def _match_keywords(text: str, keyword_groups: dict[str, list[str]]) -> str | None:
    """
    根据关键词匹配业务类型。
    """
    if not text:
        return None
    text = text.lower()
    for business_type, keywords in keyword_groups.items():
        for kw in keywords:
            if kw.lower() in text:
                return business_type
    return None


def _extract_project(text: str) -> str | None:
    """
    从摘要中提取项目名称。

    简单规则：匹配"项目:XXX"、"项目 XXX"、"project:XXX"等模式。
    """
    if not text:
        return None
    import re
    patterns = [
        r"项目[:：]\s*([^，,；;。\s]+)",
        r"project[:：]\s*([^，,；;。\s]+)",
        r"([\u4e00-\u9fa5\w]+项目)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_department(text: str) -> str | None:
    """
    从摘要中提取部门名称。
    """
    if not text:
        return None
    import re
    for dept in DEPARTMENT_KEYWORDS:
        if dept in text:
            # 尝试提取"XX部"或"XX中心"
            match = re.search(r"([\u4e00-\u9fa5\w]+(?:部|中心))", text)
            if match:
                return match.group(1).strip()
    return None


def suggest_tags_for_entry(
    db: Session,
    ledger_id: int,
    entry: dict[str, Any],
    auto_create_categories: bool = True,
) -> list[TagSuggestion]:
    """
    为单条分录生成智能标签建议。

    Args:
        db: 数据库会话
        ledger_id: 账簿 ID
        entry: 分录信息字典，需包含 account_code, account_name, summary,
               debit_amount, credit_amount, counterparty, counterparty_id 等
        auto_create_categories: 是否自动创建不存在的 TagCategory

    Returns:
        TagSuggestion 列表
    """
    suggestions: list[TagSuggestion] = []
    summary = entry.get("summary") or ""
    account_code = entry.get("account_code") or ""
    account_name = entry.get("account_name") or ""
    counterparty = entry.get("counterparty") or ""
    counterparty_id = entry.get("counterparty_id")
    amount = _extract_amount(entry)

    # 1. 往来单位标签
    if counterparty:
        suggestions.append(
            TagSuggestion(
                category_code="counterparty",
                tag_value=counterparty,
                display_name=counterparty,
                weight=1.5,
                confidence=0.95,
                tag_source="rule",
                value_id=counterparty_id,
            )
        )

    # 2. 科目分类标签
    if account_code:
        first_digit = account_code[0]
        if first_digit in ACCOUNT_CATEGORY_RULES:
            category_value, display = ACCOUNT_CATEGORY_RULES[first_digit]
            suggestions.append(
                TagSuggestion(
                    category_code="account_category",
                    tag_value=category_value,
                    display_name=display,
                    weight=1.0,
                    confidence=0.95,
                    tag_source="rule",
                )
            )

    # 3. 业务类型标签（基于摘要和科目名称）
    combined_text = f"{summary} {account_name}"
    business_type = _match_keywords(combined_text, BUSINESS_TYPE_KEYWORDS)
    if business_type:
        suggestions.append(
            TagSuggestion(
                category_code="business_type",
                tag_value=business_type,
                display_name=business_type,
                weight=1.2,
                confidence=0.85,
                tag_source="rule",
            )
        )

    # 4. 金额规模标签
    for threshold, scale_name in AMOUNT_SCALE_RULES:
        if amount >= threshold:
            suggestions.append(
                TagSuggestion(
                    category_code="amount_scale",
                    tag_value=scale_name,
                    display_name=scale_name,
                    weight=0.8,
                    confidence=0.9,
                    tag_source="rule",
                )
            )
            break

    # 5. 项目标签
    project_name = _extract_project(summary)
    if project_name:
        suggestions.append(
            TagSuggestion(
                category_code="project",
                tag_value=project_name,
                display_name=project_name,
                weight=1.3,
                confidence=0.75,
                tag_source="rule",
            )
        )

    # 6. 部门标签
    department_name = _extract_department(summary)
    if department_name:
        suggestions.append(
            TagSuggestion(
                category_code="department",
                tag_value=department_name,
                display_name=department_name,
                weight=1.0,
                confidence=0.7,
                tag_source="rule",
            )
        )

    if auto_create_categories:
        for suggestion in suggestions:
            get_or_create_category(
                db,
                ledger_id=ledger_id,
                code=suggestion.category_code,
                name=suggestion.category_code,
                value_type="text",
            )

    return suggestions


def apply_auto_tags_to_voucher_lines(
    db: Session,
    ledger_id: int | None,
    lines: list[Any],
) -> None:
    """
    为 VoucherEntryLine 列表自动填充标签建议。

    注意：
        此函数直接修改 line.tags 列表，后续 create_voucher 会读取并持久化。
    """
    if ledger_id is None:
        return

    for line in lines:
        entry = {
            "account_code": line.account_code,
            "account_name": line.account_name,
            "summary": line.summary,
            "debit_amount": line.debit_amount,
            "credit_amount": line.credit_amount,
            "counterparty": line.counterparty,
            "counterparty_id": line.counterparty_id,
        }
        suggestions = suggest_tags_for_entry(db, ledger_id, entry)
        existing_tags = [t.get("tag_value") or t.get("tag_name") for t in (line.tags or [])]
        for suggestion in suggestions:
            if suggestion.tag_value in existing_tags:
                continue
            line.tags.append({
                "category_code": suggestion.category_code,
                "tag_value": suggestion.tag_value,
                "display_name": suggestion.display_name,
                "weight": suggestion.weight,
                "confidence": suggestion.confidence,
                "tag_source": suggestion.tag_source,
                "value_id": suggestion.value_id,
                "reviewed_by_user": False,
            })


def apply_auto_tags_to_entries(
    db: Session,
    ledger_id: int,
    entries: list[dict[str, Any]],
) -> dict[int, list[TagSuggestion]]:
    """
    为一组分录字典生成标签建议。

    常用于导入流程，在 create_voucher 之前为原始 entry 数据预生成标签。

    Returns:
        {entry_index: TagSuggestion 列表}
    """
    result: dict[int, list[TagSuggestion]] = {}
    for idx, entry in enumerate(entries):
        suggestions = suggest_tags_for_entry(db, ledger_id, entry)
        result[idx] = suggestions
    return result
