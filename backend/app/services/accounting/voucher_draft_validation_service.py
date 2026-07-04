# -*- coding: utf-8 -*-
"""
模块功能：凭证草稿端到端统一校验服务。
业务场景：用户确认候选凭证草稿后、落库为正式凭证草稿前，
         对整张批次的每张草稿执行确定性规则校验，确保数据完整性和财务正确性。
政策依据：会计准则对记账凭证完整性、借贷平衡、会计期间控制的要求。
输入数据：候选凭证草稿列表（来自前端确认后的 drafts）。
输出结果：VoucherDraftValidationReport 校验报告，包含按 draft_index 组织的错误列表。
创建日期：2026-07-02
更新记录：
    2026-07-02  初始创建，覆盖 6 类核心校验规则。
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AccountingPeriod, ChartOfAccounts, Voucher


# =============================================================================
# 错误码常量
# =============================================================================

class DraftErrorCode:
    """凭证草稿校验错误码。"""

    VOUCHER_NO_EMPTY = "VOUCHER_NO_EMPTY"
    VOUCHER_NO_DUPLICATE = "VOUCHER_NO_DUPLICATE"
    VOUCHER_DATE_INVALID = "VOUCHER_DATE_INVALID"
    PERIOD_NOT_FOUND = "PERIOD_NOT_FOUND"
    PERIOD_CLOSED = "PERIOD_CLOSED"
    PERIOD_DATE_MISMATCH = "PERIOD_DATE_MISMATCH"
    LINES_TOO_FEW = "LINES_TOO_FEW"
    ACCOUNT_CODE_EMPTY = "ACCOUNT_CODE_EMPTY"
    ACCOUNT_NOT_FOUND = "ACCOUNT_NOT_FOUND"
    AMOUNT_NEGATIVE = "AMOUNT_NEGATIVE"
    AMOUNT_BOTH_SIDES = "AMOUNT_BOTH_SIDES"
    AMOUNT_ZERO = "AMOUNT_ZERO"
    AMOUNT_PRECISION = "AMOUNT_PRECISION"
    BALANCE_MISMATCH = "BALANCE_MISMATCH"


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class DraftValidationError:
    """单条校验错误。"""

    draft_index: int
    code: str
    message: str
    field: str | None = None


@dataclass
class VoucherDraftValidationReport:
    """凭证草稿校验报告。"""

    is_valid: bool
    errors: list[DraftValidationError] = field(default_factory=list)

    def add_error(
        self,
        draft_index: int,
        code: str,
        message: str,
        field: str | None = None,
    ) -> None:
        """添加一条错误记录。"""
        self.errors.append(
            DraftValidationError(
                draft_index=draft_index,
                code=code,
                message=message,
                field=field,
            )
        )
        self.is_valid = False


# =============================================================================
# 金额处理工具
# =============================================================================

def _to_decimal(value: Any, *, field_name: str = "金额") -> Decimal | None:
    """
    将任意值转换为 Decimal，失败时返回 None。

    Args:
        value: 待转换值。
        field_name: 字段名称，用于错误提示。

    Returns:
        Decimal | None: 转换成功返回 Decimal，失败返回 None。
    """
    if value is None or value == "":
        return Decimal("0.00")
    try:
        return Decimal(str(value)).quantize(Decimal("0.00"))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _has_two_decimal_places(value: Decimal) -> bool:
    """检查 Decimal 是否精确到 2 位小数。"""
    return value == value.quantize(Decimal("0.00"))


# =============================================================================
# 校验函数
# =============================================================================

def _parse_voucher_date(
    draft: dict[str, Any],
    draft_index: int,
    report: VoucherDraftValidationReport,
) -> date | None:
    """解析并校验凭证日期。"""
    raw_date = draft.get("voucher_date")
    if not raw_date:
        report.add_error(
            draft_index=draft_index,
            code=DraftErrorCode.VOUCHER_DATE_INVALID,
            message="凭证日期不能为空",
            field="voucher_date",
        )
        return None

    if isinstance(raw_date, date):
        return raw_date

    try:
        return date.fromisoformat(str(raw_date))
    except ValueError:
        report.add_error(
            draft_index=draft_index,
            code=DraftErrorCode.VOUCHER_DATE_INVALID,
            message=f"凭证日期格式不正确：{raw_date}",
            field="voucher_date",
        )
        return None


def _validate_voucher_no(
    draft: dict[str, Any],
    draft_index: int,
    report: VoucherDraftValidationReport,
    seen_voucher_nos: set[str],
) -> str | None:
    """校验凭证号非空、同批次不重复。"""
    voucher_no = str(draft.get("voucher_no") or "").strip()
    if not voucher_no:
        report.add_error(
            draft_index=draft_index,
            code=DraftErrorCode.VOUCHER_NO_EMPTY,
            message="凭证号不能为空",
            field="voucher_no",
        )
        return None

    if voucher_no in seen_voucher_nos:
        report.add_error(
            draft_index=draft_index,
            code=DraftErrorCode.VOUCHER_NO_DUPLICATE,
            message=f"凭证号 {voucher_no} 在同批次中重复",
            field="voucher_no",
        )
        return None

    seen_voucher_nos.add(voucher_no)
    return voucher_no


def _validate_period(
    db: Session,
    ledger_id: int,
    voucher_date: date,
    draft_index: int,
    report: VoucherDraftValidationReport,
) -> int | None:
    """校验凭证日期落在 open/reopened 的会计期间内。"""
    period = (
        db.query(AccountingPeriod)
        .filter(
            AccountingPeriod.ledger_id == ledger_id,
            AccountingPeriod.start_date <= voucher_date,
            AccountingPeriod.end_date >= voucher_date,
        )
        .order_by(AccountingPeriod.start_date.desc())
        .first()
    )

    if not period:
        report.add_error(
            draft_index=draft_index,
            code=DraftErrorCode.PERIOD_NOT_FOUND,
            message=f"凭证日期 {voucher_date} 未找到匹配的会计期间",
            field="voucher_date",
        )
        return None

    if period.status not in {"open", "reopened"}:
        report.add_error(
            draft_index=draft_index,
            code=DraftErrorCode.PERIOD_CLOSED,
            message=f"会计期间 {period.period_code} 状态为 {period.status}，不能录入凭证",
            field="voucher_date",
        )
        return None

    return period.id


def _validate_lines(
    db: Session,
    ledger_id: int,
    draft: dict[str, Any],
    draft_index: int,
    report: VoucherDraftValidationReport,
) -> tuple[Decimal, Decimal] | None:
    """校验分录行，返回（借方合计，贷方合计）。"""
    lines = draft.get("lines", [])
    if not isinstance(lines, list):
        report.add_error(
            draft_index=draft_index,
            code=DraftErrorCode.LINES_TOO_FEW,
            message="分录行格式不正确，应为列表",
            field="lines",
        )
        return None

    if len(lines) < 2:
        report.add_error(
            draft_index=draft_index,
            code=DraftErrorCode.LINES_TOO_FEW,
            message=f"分录行数不能少于 2 行，当前 {len(lines)} 行",
            field="lines",
        )
        return None

    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")

    for line_index, line in enumerate(lines):
        if not isinstance(line, dict):
            report.add_error(
                draft_index=draft_index,
                code=DraftErrorCode.LINES_TOO_FEW,
                message=f"第 {line_index + 1} 行格式不正确",
                field=f"lines[{line_index}]",
            )
            continue

        account_code = str(line.get("account_code") or "").strip()
        if not account_code:
            report.add_error(
                draft_index=draft_index,
                code=DraftErrorCode.ACCOUNT_CODE_EMPTY,
                message=f"第 {line_index + 1} 行科目编码不能为空",
                field=f"lines[{line_index}].account_code",
            )
        else:
            account = (
                db.query(ChartOfAccounts)
                .filter(
                    ChartOfAccounts.ledger_id == ledger_id,
                    ChartOfAccounts.code == account_code,
                )
                .first()
            )
            if not account:
                report.add_error(
                    draft_index=draft_index,
                    code=DraftErrorCode.ACCOUNT_NOT_FOUND,
                    message=f"第 {line_index + 1} 行科目 {account_code} 在当前账簿中不存在",
                    field=f"lines[{line_index}].account_code",
                )

        debit_amount = _to_decimal(line.get("debit_amount"))
        credit_amount = _to_decimal(line.get("credit_amount"))

        if debit_amount is None:
            report.add_error(
                draft_index=draft_index,
                code=DraftErrorCode.AMOUNT_PRECISION,
                message=f"第 {line_index + 1} 行借方金额格式不正确",
                field=f"lines[{line_index}].debit_amount",
            )
            continue

        if credit_amount is None:
            report.add_error(
                draft_index=draft_index,
                code=DraftErrorCode.AMOUNT_PRECISION,
                message=f"第 {line_index + 1} 行贷方金额格式不正确",
                field=f"lines[{line_index}].credit_amount",
            )
            continue

        if debit_amount < 0:
            report.add_error(
                draft_index=draft_index,
                code=DraftErrorCode.AMOUNT_NEGATIVE,
                message=f"第 {line_index + 1} 行借方金额不能为负数",
                field=f"lines[{line_index}].debit_amount",
            )
        if credit_amount < 0:
            report.add_error(
                draft_index=draft_index,
                code=DraftErrorCode.AMOUNT_NEGATIVE,
                message=f"第 {line_index + 1} 行贷方金额不能为负数",
                field=f"lines[{line_index}].credit_amount",
            )

        if debit_amount > 0 and credit_amount > 0:
            report.add_error(
                draft_index=draft_index,
                code=DraftErrorCode.AMOUNT_BOTH_SIDES,
                message=f"第 {line_index + 1} 行不能同时填写借方和贷方金额",
                field=f"lines[{line_index}].debit_amount",
            )

        if debit_amount == 0 and credit_amount == 0:
            report.add_error(
                draft_index=draft_index,
                code=DraftErrorCode.AMOUNT_ZERO,
                message=f"第 {line_index + 1} 行借方或贷方金额至少填写一项",
                field=f"lines[{line_index}].debit_amount",
            )

        total_debit += debit_amount
        total_credit += credit_amount

    return total_debit, total_credit


def _check_balance(
    total_debit: Decimal,
    total_credit: Decimal,
    draft_index: int,
    report: VoucherDraftValidationReport,
) -> None:
    """校验借贷平衡。"""
    if total_debit != total_credit:
        report.add_error(
            draft_index=draft_index,
            code=DraftErrorCode.BALANCE_MISMATCH,
            message=f"借贷不平衡：借方合计 {total_debit}，贷方合计 {total_credit}，差额 {total_debit - total_credit}",
            field="lines",
        )


# =============================================================================
# 主校验函数
# =============================================================================

def validate_voucher_drafts(
    db: Session,
    *,
    ledger_id: int,
    organization_id: int,
    drafts: list[Any],
) -> VoucherDraftValidationReport:
    """
    对候选凭证草稿列表执行端到端统一校验。

    业务逻辑：
        1. 校验每张草稿的凭证号非空、同批次不重复；
        2. 校验凭证日期格式正确且落在 open/reopened 期间内；
        3. 校验分录行数不少于 2 行；
        4. 校验科目编码非空且在账簿中存在；
        5. 校验金额非负、不能同时有借贷、至少有一方非零；
        6. 校验单张草稿借贷平衡；
        7. 校验凭证号在账簿内不与已有凭证重复。

    Args:
        db: 数据库会话。
        ledger_id: 账簿 ID。
        organization_id: 组织 ID（预留，用于后续扩展）。
        drafts: 候选凭证草稿列表。

    Returns:
        VoucherDraftValidationReport: 校验报告，is_valid=True 表示全部通过。
    """
    report = VoucherDraftValidationReport(is_valid=True)

    if not drafts:
        report.add_error(
            draft_index=-1,
            code="DRAFTS_EMPTY",
            message="草稿列表为空",
            field="drafts",
        )
        return report

    seen_voucher_nos: set[str] = set()
    voucher_nos_to_check: list[tuple[int, str]] = []

    for draft_index, draft in enumerate(drafts):
        if not isinstance(draft, dict):
            report.add_error(
                draft_index=draft_index,
                code="DRAFT_FORMAT_ERROR",
                message="草稿格式不正确，应为字典",
                field=f"drafts[{draft_index}]",
            )
            continue

        # 1. 凭证号校验
        voucher_no = _validate_voucher_no(draft, draft_index, report, seen_voucher_nos)
        if voucher_no:
            voucher_nos_to_check.append((draft_index, voucher_no))

        # 2. 凭证日期和期间校验
        voucher_date = _parse_voucher_date(draft, draft_index, report)
        if voucher_date:
            _validate_period(db, ledger_id, voucher_date, draft_index, report)

        # 3. 分录行校验与借贷平衡
        result = _validate_lines(db, ledger_id, draft, draft_index, report)
        if result is not None:
            total_debit, total_credit = result
            _check_balance(total_debit, total_credit, draft_index, report)

    # 4. 校验凭证号在账簿内是否已存在
    if voucher_nos_to_check:
        existing_vouchers = (
            db.query(Voucher.voucher_no)
            .filter(
                Voucher.ledger_id == ledger_id,
                Voucher.voucher_no.in_([vn for _, vn in voucher_nos_to_check]),
            )
            .all()
        )
        existing_nos = {row.voucher_no for row in existing_vouchers}
        for draft_index, voucher_no in voucher_nos_to_check:
            if voucher_no in existing_nos:
                report.add_error(
                    draft_index=draft_index,
                    code=DraftErrorCode.VOUCHER_NO_DUPLICATE,
                    message=f"凭证号 {voucher_no} 在当前账簿中已存在",
                    field="voucher_no",
                )

    return report
