from typing import Any

from app.db.models import AccountingEntry


# 凭证字定义
VOUCHER_TYPES = {
    "银": "银行转账类凭证",
    "现": "现金业务类凭证",
    "转": "转账/计提/摊销类凭证",
    "记": "通用记账凭证",
}

# 凭证字识别规则
VOUCHER_TYPE_PATTERNS = {
    "银": {
        "keywords": [
            # 银行相关科目
            "银行存款", "工商银行", "农业银行", "建设银行", "中国银行", "交通银行",
            "招商银行", "浦发银行", "兴业银行", "民生银行", "光大银行",
            "银行", "账户", "开户行", "转账", "汇款", "支票", "承兑",
            # 摘要关键词
            "转账", "汇款", "付款", "收款", "提现", "存款", "贷款", "利息",
            "手续费", "电汇", "网银", "pos", "刷卡",
        ],
        "weight": 1.0,
    },
    "现": {
        "keywords": [
            # 现金相关科目
            "库存现金", "现金",
            # 摘要关键词
            "现金", "提款", "备用金", "报销", "差旅费", "工资", "奖金",
            "津贴", "补贴", "押金", "还款", "借款",
        ],
        "weight": 1.0,
    },
    "转": {
        "keywords": [
            # 计提/摊销相关
            "计提", "摊销", "预提", "分配", "结转", "结汇",
            "折旧", "摊销", "减值", "准备", "调整",
            "工资分配", "福利费", "社保", "公积金",
            "制造费用", "生产成本", "完工入库",
            # 内部转账
            "内部调拨", "调拨",
        ],
        "weight": 1.0,
    },
    "记": {
        "keywords": [
            # 通用记账
            "记", "记账", "录入",
        ],
        "weight": 0.5,  # 权重较低，作为兜底选项
    },
}


def suggest_voucher_type(entry: AccountingEntry) -> tuple[str | None, float]:
    """
    根据分录内容推荐凭证字

    Returns:
        (凭证字, 置信度) 或 (None, 0)
    """
    summary = (entry.summary or "").lower()
    account = (entry.account_name or "").lower()
    combined_text = f"{summary} {account}"

    scores: dict[str, float] = {}

    for voucher_type, config in VOUCHER_TYPE_PATTERNS.items():
        score = 0
        matched_keywords = []

        for keyword in config["keywords"]:
            if keyword.lower() in combined_text:
                score += config["weight"]
                matched_keywords.append(keyword)

        if matched_keywords:
            scores[voucher_type] = score

    if not scores:
        return None, 0.0

    # 返回得分最高的凭证字
    best_type = max(scores, key=scores.get)
    max_score = scores[best_type]

    # 计算置信度（归一化到 0-1）
    confidence = min(max_score / 3.0, 1.0) if max_score > 0 else 0.0

    return best_type, confidence


def suggest_voucher_type_reason(entry: AccountingEntry) -> str | None:
    """
    返回凭证字推荐的原因
    """
    voucher_type, confidence = suggest_voucher_type(entry)
    if not voucher_type or confidence < 0.3:
        return None

    summary = (entry.summary or "").lower()
    account = (entry.account_name or "").lower()
    combined_text = f"{summary} {account}"

    matched = []
    for keyword in VOUCHER_TYPE_PATTERNS.get(voucher_type, {}).get("keywords", []):
        if keyword.lower() in combined_text:
            matched.append(keyword)

    if matched:
        return f"根据关键词「{', '.join(matched[:3])}」推荐"

    return None


def suggest_tags(entry: AccountingEntry) -> list[tuple[str, float]]:
    """推荐标签"""
    tags: list[tuple[str, float]] = []
    amount = float(entry.debit_amount or entry.credit_amount or 0)
    summary = entry.summary or ""
    account = entry.account_name or ""

    # 凭证字推荐（作为特殊标签）
    voucher_type, confidence = suggest_voucher_type(entry)
    if voucher_type and confidence >= 0.3:
        tags.append((f"凭证字:{voucher_type}", confidence))

    # 大额交易
    if amount >= 100000:
        tags.append(("大额交易", 0.9))
    if amount >= 500000:
        tags.append(("特大额交易", 0.95))

    # 期末交易
    if entry.voucher_date and entry.voucher_date.month in {12, 1}:
        tags.append(("期末交易", 0.75))

    # 摘要异常
    if len(summary.strip()) < 4:
        tags.append(("摘要异常", 0.85))
    if summary.strip() in ["无", "暂无", "-", "."]:
        tags.append(("无效摘要", 0.9))

    # 往来挂账
    if any(word in account for word in ["其他应收", "其他应付", "往来", "预付", "预收"]):
        tags.append(("往来挂账", 0.75))

    # 需要人工复核
    if any(word in summary for word in ["咨询", "服务", "会议", "礼品", "招待", "餐饮"]):
        tags.append(("需人工复核", 0.7))

    return tags
