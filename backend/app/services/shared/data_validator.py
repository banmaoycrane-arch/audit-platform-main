"""
数据验证与质量评分服务

对导入的会计分录进行质量评估
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.services.doc_parsing.format_template import STANDARD_FIELDS


@dataclass
class ValidationIssue:
    """验证问题"""
    issue_type: str  # missing_required, invalid_format, suspicious_value, etc.
    field: str
    value: Any
    message: str
    severity: str = "warning"  # info, warning, error


@dataclass
class EntryQuality:
    """单条分录质量评分"""
    entry_index: int
    overall_score: float  # 0-100
    field_scores: dict[str, float]  # 各字段分数
    issues: list[ValidationIssue]
    warnings: list[str]


@dataclass
class ImportQualityReport:
    """导入质量报告"""
    total_entries: int
    valid_entries: int
    invalid_entries: int
    overall_score: float  # 0-100
    entry_scores: list[EntryQuality]
    field_stats: dict[str, dict[str, Any]]  # 各字段统计
    common_issues: dict[str, int]  # 常见问题统计
    recommendations: list[str]


# 必填字段
REQUIRED_FIELDS = ["summary", "account_name"]

# 字段权重
FIELD_WEIGHTS = {
    "voucher_no": 0.1,
    "voucher_date": 0.1,
    "summary": 0.25,
    "account_code": 0.1,
    "account_name": 0.25,
    "debit_amount": 0.1,
    "credit_amount": 0.1,
    "counterparty": 0.0,
}

# 异常模式
SUSPICIOUS_PATTERNS = {
    "large_round_amount": (100000, "大额整数金额"),
    "weak_summary": (4, "摘要过短"),
    "unusual_counterparty": (None, "非常规往来单位"),
    "future_date": (None, "未来日期"),
    "end_of_period": (None, "期末大额交易"),
    "same_amount_repeat": (3, "相同金额重复"),
}


def validate_required_field(value: Any, field_name: str) -> ValidationIssue | None:
    """验证必填字段"""
    if value is None or (isinstance(value, str) and not value.strip()):
        return ValidationIssue(
            issue_type="missing_required",
            field=field_name,
            value=value,
            message=f"必填字段 {STANDARD_FIELDS.get(field_name, field_name)} 不能为空",
            severity="error",
        )
    return None


def validate_amount(amount: float, field_name: str) -> list[ValidationIssue]:
    """验证金额字段"""
    issues = []

    if amount < 0:
        issues.append(ValidationIssue(
            issue_type="negative_amount",
            field=field_name,
            value=amount,
            message=f"{STANDARD_FIELDS.get(field_name, field_name)} 不能为负数",
            severity="warning",
        ))

    if amount > 1_000_000_000:
        issues.append(ValidationIssue(
            issue_type="unrealistic_amount",
            field=field_name,
            value=amount,
            message=f"金额过大（>{amount:,.0f}），请核实",
            severity="warning",
        ))

    # 检查大额整数
    if amount >= 100000 and amount == int(amount):
        issues.append(ValidationIssue(
            issue_type="large_round_amount",
            field=field_name,
            value=amount,
            message=f"大额整数金额 {amount:,.0f}，建议复核",
            severity="info",
        ))

    return issues


def validate_date(date_value: date | None, field_name: str) -> list[ValidationIssue]:
    """验证日期字段"""
    issues: list[ValidationIssue] = []

    if date_value is None:
        return issues

    today = date.today()

    # 检查未来日期
    if date_value > today:
        issues.append(ValidationIssue(
            issue_type="future_date",
            field=field_name,
            value=date_value,
            message=f"日期 {date_value} 在未来，请核实",
            severity="warning",
        ))

    # 检查超老日期
    if date_value.year < 1990:
        issues.append(ValidationIssue(
            issue_type="historical_date",
            field=field_name,
            value=date_value,
            message=f"日期 {date_value} 过于久远，请核实",
            severity="info",
        ))

    return issues


def validate_summary(summary: str) -> list[ValidationIssue]:
    """验证摘要字段"""
    issues: list[ValidationIssue] = []

    if not summary:
        return issues

    # 检查摘要过短
    if len(summary.strip()) < 4:
        issues.append(ValidationIssue(
            issue_type="weak_summary",
            field="summary",
            value=summary,
            message=f"摘要过短（{len(summary)}字符）：{summary}",
            severity="warning",
        ))

    # 检查通用摘要
    generic_summaries = ["无", "暂无", "-", ".", "测试", "test"]
    if summary.strip().lower() in generic_summaries:
        issues.append(ValidationIssue(
            issue_type="generic_summary",
            field="summary",
            value=summary,
            message=f"通用摘要：{summary}",
            severity="warning",
        ))

    return issues


def validate_entry(entry: dict[str, Any], entry_index: int) -> EntryQuality:
    """验证单条分录"""
    issues: list[ValidationIssue] = []
    field_scores: dict[str, float] = {}

    # 验证必填字段
    for field_name in REQUIRED_FIELDS:
        value = entry.get(field_name)
        issue = validate_required_field(value, field_name)
        if issue:
            issues.append(issue)
            field_scores[field_name] = 0.0
        else:
            field_scores[field_name] = 100.0

    # 验证金额
    debit = entry.get("debit_amount", 0)
    credit = entry.get("credit_amount", 0)

    if debit > 0 and credit > 0:
        issues.append(ValidationIssue(
            issue_type="both_debit_credit",
            field="amount",
            value={"debit": debit, "credit": credit},
            message="借方和贷方同时有值，请核实",
            severity="error",
        ))
        field_scores["debit_amount"] = 0.0
        field_scores["credit_amount"] = 0.0
    elif debit == 0 and credit == 0:
        issues.append(ValidationIssue(
            issue_type="zero_amount",
            field="amount",
            value=0,
            message="借方和贷方均为零",
            severity="warning",
        ))
        field_scores["debit_amount"] = 50.0
        field_scores["credit_amount"] = 50.0
    else:
        issues.extend(validate_amount(debit, "debit_amount"))
        issues.extend(validate_amount(credit, "credit_amount"))
        field_scores["debit_amount"] = 100.0 if debit > 0 else 80.0
        field_scores["credit_amount"] = 100.0 if credit > 0 else 80.0

    # 验证日期
    voucher_date = entry.get("voucher_date")
    if voucher_date:
        issues.extend(validate_date(voucher_date, "voucher_date"))
        field_scores["voucher_date"] = 100.0
    else:
        field_scores["voucher_date"] = 80.0  # 日期可选

    # 验证摘要
    summary = entry.get("summary", "")
    issues.extend(validate_summary(summary))

    # 计算字段分数（已设置）
    for field_name, weight in FIELD_WEIGHTS.items():
        if field_name not in field_scores:
            field_scores[field_name] = 100.0

    # 计算总分
    overall_score = sum(
        field_scores.get(field_name, 100.0) * weight
        for field_name, weight in FIELD_WEIGHTS.items()
    )

    return EntryQuality(
        entry_index=entry_index,
        overall_score=overall_score,
        field_scores=field_scores,
        issues=issues,
        warnings=[issue.message for issue in issues if issue.severity in ("warning", "info")],
    )


def generate_quality_report(entries: list[dict[str, Any]], file_results: list[Any] | None = None) -> ImportQualityReport:
    """生成导入质量报告"""
    if not entries:
        return ImportQualityReport(
            total_entries=0,
            valid_entries=0,
            invalid_entries=0,
            overall_score=0.0,
            entry_scores=[],
            field_stats={},
            common_issues={},
            recommendations=["无数据可分析"],
        )

    entry_scores: list[EntryQuality] = []
    valid_count = 0
    invalid_count = 0
    issue_counts: dict[str, int] = {}
    field_stats: dict[str, dict[str, Any]] = {}

    # 初始化字段统计
    for field_name in STANDARD_FIELDS:
        field_stats[field_name] = {
            "total": 0,
            "filled": 0,
            "empty": 0,
            "unique_values": set(),
        }

    # 统计金额
    amounts = []

    for idx, entry in enumerate(entries):
        quality = validate_entry(entry, idx)
        entry_scores.append(quality)

        if quality.overall_score >= 70:
            valid_count += 1
        else:
            invalid_count += 1

        # 统计问题
        for issue in quality.issues:
            issue_type = issue.issue_type
            issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1

        # 统计字段
        for field_name in STANDARD_FIELDS:
            value = entry.get(field_name)
            field_stats[field_name]["total"] += 1
            if value and (not isinstance(value, str) or value.strip()):
                field_stats[field_name]["filled"] += 1
                if isinstance(value, (str, int, float)):
                    field_stats[field_name]["unique_values"].add(str(value))
            else:
                field_stats[field_name]["empty"] += 1

        # 收集金额
        if entry.get("debit_amount"):
            amounts.append(entry["debit_amount"])
        if entry.get("credit_amount"):
            amounts.append(entry["credit_amount"])

    # 计算总体分数
    overall_score = sum(q.overall_score for q in entry_scores) / len(entry_scores)

    # 转换 unique_values 为列表
    for field_name in field_stats:
        field_stats[field_name]["unique_values"] = list(field_stats[field_name]["unique_values"])[:100]  # 限制数量

    # 生成建议
    recommendations = []
    if overall_score < 70:
        recommendations.append("整体数据质量偏低，建议检查数据来源格式")
    if issue_counts.get("missing_required", 0) > len(entries) * 0.1:
        recommendations.append("存在较多必填字段缺失，建议完善数据")
    if issue_counts.get("weak_summary", 0) > len(entries) * 0.2:
        recommendations.append("摘要质量偏低，建议优化摘要填写规范")
    if issue_counts.get("large_round_amount", 0) > 0:
        recommendations.append("存在大额整数金额，建议重点复核")
    if not recommendations:
        recommendations.append("数据质量良好，可正常使用")

    return ImportQualityReport(
        total_entries=len(entries),
        valid_entries=valid_count,
        invalid_entries=invalid_count,
        overall_score=overall_score,
        entry_scores=entry_scores,
        field_stats=field_stats,
        common_issues=issue_counts,
        recommendations=recommendations,
    )


def get_quality_badge(score: float) -> tuple[str, str]:
    """获取质量等级"""
    if score >= 90:
        return "excellent", "优秀"
    elif score >= 70:
        return "good", "良好"
    elif score >= 50:
        return "fair", "一般"
    else:
        return "poor", "较差"
