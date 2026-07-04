"""
分录逻辑校验服务

检查分录的逻辑自洽性，包括：
- 摘要-科目匹配校验
- 借贷平衡校验
- 凭证字-科目匹配校验
- 风险案例匹配
"""

from dataclasses import dataclass, field
from typing import Any

from app.services.doc_parsing.summary_template_service import (
    RISK_CASES,
    match_risk_case,
    match_template,
)


@dataclass
class LogicIssue:
    """逻辑问题"""
    issue_type: str  # mismatch/suspicious/unbalanced/inconsistent
    severity: str  # error/warning/info
    message: str
    suggestion: str
    matched_case: dict[str, Any] | None = None


@dataclass
class LogicCheckResult:
    """逻辑校验结果"""
    entry_index: int
    is_consistent: bool
    issues: list[LogicIssue] = field(default_factory=list)
    matched_template: dict[str, Any] | None = None
    matched_risk_cases: list[dict[str, Any]] = field(default_factory=list)


def _check_summary_account_match(
    summary: str,
    debit_account: str,
    credit_account: str,
) -> list[LogicIssue]:
    """检查摘要-科目匹配"""
    issues = []

    # 检查摘要关键词与科目的对应关系
    summary_lower = summary.lower()

    # 货款相关检查
    if any(kw in summary_lower for kw in ["货款", "销售款", "销售收回"]):
        if not any(kw in credit_account.lower() for kw in ["收入", "销项", "应收"]):
            issues.append(LogicIssue(
                issue_type="mismatch",
                severity="error",
                message="摘要为收到货款，但贷方不是收入类科目",
                suggestion="贷方应为：主营业务收入、应交税费等",
            ))

    if any(kw in summary_lower for kw in ["采购", "购货", "进货"]):
        if not any(kw in debit_account.lower() for kw in ["物资", "商品", "成本", "应付"]):
            issues.append(LogicIssue(
                issue_type="mismatch",
                severity="warning",
                message="摘要为采购付款，但借方不是资产/应付类科目",
                suggestion="借方应为：在途物资、原材料、库存商品、应付账款等",
            ))

    # 费用相关检查
    if any(kw in summary_lower for kw in ["费用", "手续费", "佣金"]):
        if not any(kw in debit_account.lower() for kw in ["管理费用", "销售费用", "财务费用"]):
            if "应付账款" in debit_account.lower() or "预付账款" in debit_account.lower():
                issues.append(LogicIssue(
                    issue_type="suspicious",
                    severity="warning",
                    message="摘要为支付费用，但借方为往来科目",
                    suggestion="核实款项性质是否为预付款项",
                ))

    # 计提相关检查
    if any(kw in summary_lower for kw in ["计提", "提取"]):
        if "银行存款" in debit_account.lower():
            issues.append(LogicIssue(
                issue_type="mismatch",
                severity="error",
                message="计提分录借方不应为银行存款",
                suggestion="借方应为：管理费用、销售费用等",
            ))

    # 结转相关检查
    if any(kw in summary_lower for kw in ["结转"]):
        if "成本" in summary_lower:
            if "库存商品" in debit_account.lower():
                issues.append(LogicIssue(
                    issue_type="mismatch",
                    severity="error",
                    message="结转成本但借方为库存商品，借贷方向可能错误",
                    suggestion="借方应为主营业务成本，贷方应为库存商品",
                ))

    # 折旧相关检查
    if any(kw in summary_lower for kw in ["折旧"]):
        if "银行存款" in debit_account.lower():
            issues.append(LogicIssue(
                issue_type="mismatch",
                severity="error",
                message="计提折旧借方不应为银行存款",
                suggestion="借方应为：管理费用、制造费用等",
            ))

    return issues


def _check_voucher_account_match(
    voucher_type: str,
    debit_account: str,
    credit_account: str,
) -> list[LogicIssue]:
    """检查凭证字-科目匹配"""
    issues = []

    debit_lower = debit_account.lower()
    credit_lower = credit_account.lower()

    # 银字凭证检查
    if voucher_type == "银":
        # 银字凭证应该涉及银行存款
        if "银行" not in debit_lower and "银行" not in credit_lower:
            issues.append(LogicIssue(
                issue_type="suspicious",
                severity="info",
                message="银字凭证未涉及银行存款科目",
                suggestion="银字凭证通常涉及银行存款",
            ))

    # 现字凭证检查
    if voucher_type == "现":
        # 现字凭证应该涉及现金或银行存款
        if "现金" not in debit_lower and "现金" not in credit_lower:
            if "银行" not in debit_lower and "银行" not in credit_lower:
                issues.append(LogicIssue(
                    issue_type="suspicious",
                    severity="info",
                    message="现字凭证未涉及现金或银行存款科目",
                    suggestion="现字凭证通常涉及库存现金或银行存款",
                ))

    # 转字凭证检查
    if voucher_type == "转":
        # 转字凭证不应涉及银行/现金
        if "银行" in debit_lower or "银行" in credit_lower or "现金" in debit_lower or "现金" in credit_lower:
            issues.append(LogicIssue(
                issue_type="suspicious",
                severity="info",
                message="转字凭证涉及银行/现金科目",
                suggestion="转字凭证通常为内部转账计提，不涉及资金变动",
            ))

    return issues


def _check_balance(
    debit_amount: float | list[float],
    credit_amount: float | list[float],
) -> list[LogicIssue]:
    """检查借贷平衡"""
    issues = []

    if isinstance(debit_amount, (int, float)) and isinstance(credit_amount, (int, float)):
        diff = abs(debit_amount - credit_amount)
        if diff > 0.01:  # 允许小数误差
            issues.append(LogicIssue(
                issue_type="unbalanced",
                severity="error",
                message=f"借贷不平衡：借方 {debit_amount} vs 贷方 {credit_amount}",
                suggestion="请检查借贷方金额是否相等",
            ))
    elif isinstance(debit_amount, list) and isinstance(credit_amount, list):
        debit_sum = sum(d for d in debit_amount if d)
        credit_sum = sum(c for c in credit_amount if c)
        diff = abs(debit_sum - credit_sum)
        if diff > 0.01:
            issues.append(LogicIssue(
                issue_type="unbalanced",
                severity="error",
                message=f"借贷不平衡：借方合计 {debit_sum} vs 贷方合计 {credit_sum}",
                suggestion="请检查借贷方金额是否相等",
            ))

    return issues


def _check_amount_consistency(
    amount: float,
    summary: str,
    debit_account: str,
) -> list[LogicIssue]:
    """检查金额与摘要一致性"""
    issues = []

    summary_lower = summary.lower()
    debit_lower = debit_account.lower()

    # 大额但摘要模糊
    if amount > 100000 and len(summary.strip()) < 4:
        issues.append(LogicIssue(
            issue_type="suspicious",
            severity="warning",
            message=f"大额交易（{amount:,.2f}）但摘要过短",
            suggestion="建议完善摘要描述",
        ))

    # 大额整数金额
    if amount >= 100000 and amount == int(amount):
        issues.append(LogicIssue(
            issue_type="info",
            severity="info",
            message=f"大额整数金额 {amount:,.0f}",
            suggestion="核实金额是否准确",
        ))

    # 摘要与金额明显不符
    if amount > 1000000:  # 百万以上
        if any(kw in summary_lower for kw in ["办公", "文具", "笔", "纸"]):
            issues.append(LogicIssue(
                issue_type="suspicious",
                severity="warning",
                message=f"大额交易（{amount:,.2f}）摘要为小额办公用品",
                suggestion="核实是否为分类错误或金额错误",
            ))

    return issues


def _match_risk_patterns(
    summary: str,
    debit_account: str,
    credit_account: str,
) -> list[dict[str, Any]]:
    """匹配风险模式"""
    matched_cases = match_risk_case(summary, debit_account, credit_account)
    return matched_cases


def check_entry_logic(
    entry_index: int,
    summary: str,
    debit_account: str,
    credit_account: str,
    debit_amount: float,
    credit_amount: float,
    voucher_type: str | None = None,
) -> LogicCheckResult:
    """
    校验单条分录的逻辑自洽性

    Returns:
        LogicCheckResult
    """
    issues: list[LogicIssue] = []

    # 1. 检查借贷平衡
    issues.extend(_check_balance(debit_amount, credit_amount))

    # 2. 检查摘要-科目匹配
    issues.extend(_check_summary_account_match(summary, debit_account, credit_account))

    # 3. 检查凭证字-科目匹配（如果有）
    if voucher_type:
        issues.extend(_check_voucher_account_match(voucher_type, debit_account, credit_account))

    # 4. 检查金额与摘要一致性
    issues.extend(_check_amount_consistency(
        debit_amount or credit_amount,
        summary,
        debit_account,
    ))

    # 5. 匹配风险模式
    matched_cases = _match_risk_patterns(summary, debit_account, credit_account)

    # 如果有匹配的风险案例，添加对应的问题
    for case in matched_cases:
        issues.append(LogicIssue(
            issue_type="risk_case",
            severity=case["severity"].lower(),
            message=f"【风险案例】{case['risk_description']}",
            suggestion=case["audit_suggestion"],
            matched_case=case,
        ))

    # 6. 匹配摘要模板
    matched_template = match_template(summary, debit_account, credit_account)
    best_template = matched_template[0] if matched_template else None

    # 判断是否一致
    has_error = any(i.severity == "error" for i in issues)
    has_warning = any(i.severity == "warning" for i in issues)

    is_consistent = not has_error

    return LogicCheckResult(
        entry_index=entry_index,
        is_consistent=is_consistent,
        issues=issues,
        matched_template=best_template,
        matched_risk_cases=matched_cases,
    )


def check_entries_batch(
    entries: list[dict[str, Any]],
    voucher_types: list[str] | None = None,
) -> list[LogicCheckResult]:
    """
    批量校验分录逻辑

    Args:
        entries: 分录列表
        voucher_types: 对应的凭证字列表（可选）

    Returns:
        校验结果列表
    """
    results = []

    for i, entry in enumerate(entries):
        voucher_type = voucher_types[i] if voucher_types and i < len(voucher_types) else None

        result = check_entry_logic(
            entry_index=i,
            summary=entry.get("summary", ""),
            debit_account=entry.get("debit_account", ""),
            credit_account=entry.get("credit_account", ""),
            debit_amount=entry.get("debit_amount", 0),
            credit_amount=entry.get("credit_amount", 0),
            voucher_type=voucher_type,
        )
        results.append(result)

    return results


@dataclass
class BatchCheckReport:
    """批量校验报告"""
    total_entries: int
    consistent_entries: int
    inconsistent_entries: int
    error_count: int
    warning_count: int
    info_count: int
    risk_case_count: int
    results: list[LogicCheckResult]

    @property
    def consistency_rate(self) -> float:
        """一致性比率"""
        if self.total_entries == 0:
            return 0.0
        return self.consistent_entries / self.total_entries * 100


def generate_batch_report(results: list[LogicCheckResult]) -> BatchCheckReport:
    """生成批量校验报告"""
    error_count = 0
    warning_count = 0
    info_count = 0
    risk_case_count = 0

    for result in results:
        for issue in result.issues:
            if issue.severity == "error":
                error_count += 1
            elif issue.severity == "warning":
                warning_count += 1
            elif issue.severity == "info":
                info_count += 1

        risk_case_count += len(result.matched_risk_cases)

    consistent = sum(1 for r in results if r.is_consistent)

    return BatchCheckReport(
        total_entries=len(results),
        consistent_entries=consistent,
        inconsistent_entries=len(results) - consistent,
        error_count=error_count,
        warning_count=warning_count,
        info_count=info_count,
        risk_case_count=risk_case_count,
        results=results,
    )
