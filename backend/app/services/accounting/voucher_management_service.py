# -*- coding: utf-8 -*-
from typing import Any
"""
凭证更新服务扩展模块。

业务场景：在已有 voucher_service 基础上补充整单更新、凭证号唯一性校验、
        会计期间校验等独立 /api/vouchers 接口所需能力。
政策依据：会计准则对记账凭证完整性、借贷平衡、期间控制的要求。
输入数据：凭证更新请求、账簿上下文、用户上下文。
输出结果：更新后的 Voucher 对象或业务异常。

创建日期：2026-07-01
更新记录：
    2026-07-01  初始创建，补充 update_voucher 整单更新与权限/期间校验。
"""
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, AccountingPeriod, ChartOfAccounts, Voucher
from app.models.user import User
from app.services.shared import ledger_management_service
from app.services.accounting.voucher_service import (
    VoucherEntryLine,
    VoucherNotFoundError,
    VoucherStateError,
    VoucherValidationError,
    create_voucher,
    delete_voucher,
    get_voucher_by_id,
    get_voucher_lines,
    list_vouchers,
    update_voucher_status,
    validate_voucher_balance,
)


class PeriodClosedError(VoucherValidationError):
    """会计期间已结账异常。"""
    pass


class LedgerAccessError(VoucherValidationError):
    """用户无账簿访问权限异常。"""
    pass


class VoucherDuplicateError(VoucherValidationError):
    """凭证号重复异常。"""
    pass


def _build_voucher_no(voucher_type: str, voucher_number: str) -> str:
    """
    拼装凭证号。

    业务逻辑：将凭证字与凭证号组合成唯一凭证号，兼容现有 `voucher_no` 字段。
    """
    return f"{voucher_type}-{voucher_number}"


def _split_voucher_no(voucher_no: str) -> tuple[str, str]:
    """
    拆分凭证号为凭证字和凭证号。

    业务逻辑：如果凭证号中包含 '-'，则按第一个 '-' 拆分；否则整体作为凭证号。
    """
    if "-" in voucher_no:
        voucher_type, voucher_number = voucher_no.split("-", 1)
        return voucher_type, voucher_number
    return "", voucher_no


def _get_period(db: Session, period_id: int) -> Optional[AccountingPeriod]:
    """根据ID获取会计期间。"""
    return db.get(AccountingPeriod, period_id)


def _validate_period_open(
    db: Session, period_id: int, voucher_date: date
) -> AccountingPeriod:
    """
    校验会计期间是否可录入凭证。

    业务逻辑：
    1. 期间必须存在。
    2. 期间状态必须是 open 或 reopened。
    3. 凭证日期必须在期间起止范围内。
    """
    period = _get_period(db, period_id)
    if not period:
        raise VoucherValidationError(f"会计期间 {period_id} 不存在")

    if period.status not in {"open", "reopened"}:
        raise PeriodClosedError(
            f"会计期间 {period.period_code} 已{period.status}，不能录入或修改凭证"
        )

    if voucher_date < period.start_date or voucher_date > period.end_date:
        raise VoucherValidationError(
            f"凭证日期 {voucher_date} 不在期间 {period.period_code} "
            f"({period.start_date} ~ {period.end_date}) 范围内"
        )

    return period


def _validate_voucher_no_unique(
    db: Session,
    *,
    ledger_id: int,
    voucher_no: str,
    exclude_voucher_id: Optional[int] = None,
) -> None:
    """
    校验凭证号在账簿内唯一。

    业务逻辑：同一账簿下不允许存在相同的 voucher_no，更新时排除当前凭证。
    """
    stmt = select(Voucher).where(
        Voucher.ledger_id == ledger_id, Voucher.voucher_no == voucher_no
    )
    if exclude_voucher_id:
        stmt = stmt.where(Voucher.id != exclude_voucher_id)
    existing = db.execute(stmt).scalars().first()
    if existing:
        raise VoucherDuplicateError(
            f"凭证号 {voucher_no} 在当前账簿中已存在"
        )


def _check_ledger_access(
    db: Session, user_id: int, ledger_id: int
) -> None:
    """校验用户是否有账簿访问权限。"""
    if not ledger_management_service.user_has_ledger_access(db, user_id, ledger_id):
        raise LedgerAccessError(f"用户无权访问账簿 {ledger_id}")


def _lines_from_dicts(db: Session, ledger_id: int, lines: List[dict[str, Any]]) -> List[VoucherEntryLine]:
    """
    将前端传入的分录字典转换为 VoucherEntryLine 对象。

    业务逻辑：统一字段映射，便于复用现有校验和创建逻辑。
    如果科目名称未提供，自动从科目表查询获取。
    """
    result = []
    for line in lines:
        account_code = line.get("account_code", "")
        account_name = line.get("account_name")
        if not account_name and account_code:
            account = db.query(ChartOfAccounts).filter(
                ChartOfAccounts.code == account_code,
                ChartOfAccounts.ledger_id == ledger_id,
            ).first()
            if account:
                account_name = account.name
        result.append(
            VoucherEntryLine(
                account_code=account_code,
                account_name=account_name,
                summary=line.get("summary", ""),
                debit_amount=Decimal(str(line.get("debit_amount") or 0)).quantize(
                    Decimal("0.00")
                ),
                credit_amount=Decimal(str(line.get("credit_amount") or 0)).quantize(
                    Decimal("0.00")
                ),
                counterparty=line.get("counterparty"),
                counterparty_id=line.get("counterparty_id"),
            )
        )
    return result


def create_voucher_from_request(
    db: Session,
    *,
    user: User,
    data: dict[str, Any],
) -> Voucher:
    """
    根据请求数据创建凭证。

    业务逻辑：
    1. 校验用户账簿权限。
    2. 校验会计期间状态。
    3. 校验凭证号唯一性。
    4. 校验借贷平衡。
    5. 调用 create_voucher 写入数据库。

    Args:
        db: 数据库会话
        user: 当前用户
        data: 前端请求字典，包含 ledger_id, organization_id, period_id 等字段

    Returns:
        Voucher: 新创建的凭证对象

    注意事项：
        1. 金额字段使用 Decimal 计算，避免浮点误差。
        2. 凭证号使用 voucher_type + voucher_number 拼装。
    """
    ledger_id = data["ledger_id"]
    organization_id = data["organization_id"]
    period_id = data["period_id"]
    voucher_type = data["voucher_type"]
    voucher_number = data["voucher_number"]
    voucher_date = data["voucher_date"]
    summary = data.get("summary")
    attachment_count = data.get("attachment_count", 0) or 0
    lines = data.get("lines", [])

    _check_ledger_access(db, user.id, ledger_id)
    _validate_period_open(db, period_id, voucher_date)

    voucher_no = _build_voucher_no(voucher_type, voucher_number)
    _validate_voucher_no_unique(db, ledger_id=ledger_id, voucher_no=voucher_no)

    entry_lines = _lines_from_dicts(db, ledger_id, lines)
    total_debit, total_credit = validate_voucher_balance(
        voucher_no, voucher_date, entry_lines
    )

    voucher = create_voucher(
        db,
        ledger_id=ledger_id,
        organization_id=organization_id,
        period_id=period_id,
        voucher_no=voucher_no,
        voucher_date=voucher_date,
        summary=summary,
        lines=entry_lines,
        source_type="manual",
        created_by=user.id,
        status="draft",
    )
    voucher.period_id = period_id
    voucher.attachment_count = attachment_count or 0
    db.flush()
    db.refresh(voucher)
    return voucher


def update_voucher_from_request(
    db: Session,
    *,
    user: User,
    voucher_id: int,
    data: dict[str, Any],
) -> Voucher:
    """
    根据请求数据更新整张凭证。

    业务逻辑：
    1. 仅允许修改 draft 状态凭证。
    2. 如修改期间或日期，需校验新期间状态。
    3. 如修改凭证号，需校验唯一性。
    4. 删除旧分录行，插入新分录行，保证事务一致。

    Args:
        db: 数据库会话
        user: 当前用户
        voucher_id: 凭证ID
        data: 更新数据字典

    Returns:
        Voucher: 更新后的凭证对象

    注意事项：
        1. 整单更新采用"先删后插"策略，避免分录行残留。
        2. 必须在事务内执行，确保数据一致性。
    """
    voucher = get_voucher_by_id(db, voucher_id)
    if not voucher:
        raise VoucherNotFoundError(f"凭证 {voucher_id} 不存在")

    _check_ledger_access(db, user.id, voucher.ledger_id)

    if voucher.status != "draft":
        raise VoucherStateError("只有草稿状态凭证可以编辑")

    # 确定新值，未传入则保持原值
    new_period_id = data.get("period_id") or _infer_period_id(db, voucher)
    new_voucher_type = data.get("voucher_type") or _split_voucher_no(voucher.voucher_no)[0]
    new_voucher_number = data.get("voucher_number") or _split_voucher_no(voucher.voucher_no)[1]
    new_voucher_date = data.get("voucher_date") or voucher.voucher_date
    new_summary = data.get("summary") if "summary" in data else voucher.summary
    new_attachment_count = data.get("attachment_count") if "attachment_count" in data else 0
    new_lines = data.get("lines")

    _validate_period_open(db, new_period_id, new_voucher_date)

    new_voucher_no = _build_voucher_no(new_voucher_type, new_voucher_number)
    if new_voucher_no != voucher.voucher_no:
        _validate_voucher_no_unique(
            db,
            ledger_id=voucher.ledger_id,
            voucher_no=new_voucher_no,
            exclude_voucher_id=voucher_id,
        )

    entry_lines = _lines_from_dicts(db, voucher.ledger_id, new_lines) if new_lines else None
    if entry_lines:
        total_debit, total_credit = validate_voucher_balance(
            new_voucher_no, new_voucher_date, entry_lines
        )
        voucher.total_debit = float(total_debit)
        voucher.total_credit = float(total_credit)
    else:
        # 未传入分录行时保持原借贷合计
        entry_lines = [
            VoucherEntryLine(
                account_code=entry.account_code or "",
                account_name=entry.account_name,
                summary=entry.summary or "",
                debit_amount=Decimal(str(entry.debit_amount)).quantize(Decimal("0.00")),
                credit_amount=Decimal(str(entry.credit_amount)).quantize(Decimal("0.00")),
                counterparty=entry.counterparty,
                counterparty_id=entry.counterparty_id,
            )
            for entry in get_voucher_lines(db, voucher_id)
        ]

    # 更新主表
    voucher.voucher_no = new_voucher_no
    voucher.voucher_date = new_voucher_date
    voucher.summary = new_summary
    voucher.updated_at = datetime.now(timezone.utc)
    voucher.attachment_count = new_attachment_count or 0
    db.flush()

    # 删除旧分录行
    db.query(AccountingEntry).filter(
        AccountingEntry.voucher_id == voucher_id
    ).delete(synchronize_session=False)

    # 插入新分录行
    for line_no, line in enumerate(entry_lines, start=1):
        entry = AccountingEntry(
            voucher_id=voucher.id,
            ledger_id=voucher.ledger_id,
            organization_id=voucher.organization_id,
            voucher_no=voucher.voucher_no,
            voucher_date=voucher.voucher_date,
            summary=line.summary or new_summary or "",
            account_code=line.account_code,
            account_name=line.account_name or "",
            debit_amount=line.debit_amount or Decimal("0.00"),
            credit_amount=line.credit_amount or Decimal("0.00"),
            counterparty=line.counterparty,
            counterparty_id=line.counterparty_id,
            entry_line_no=line_no,
            entry_source="manual",
            review_status="draft",
            post_status="draft",
        )
        db.add(entry)

    db.commit()
    db.refresh(voucher)
    return voucher


def _infer_period_id(db: Session, voucher: Voucher) -> int:
    """
    根据凭证日期推断会计期间ID。

    业务逻辑：更新时未传入 period_id，则根据 voucher_date 查找匹配的 open/reopened 期间。
    """
    period = (
        db.query(AccountingPeriod)
        .filter(
            AccountingPeriod.ledger_id == voucher.ledger_id,
            AccountingPeriod.start_date <= voucher.voucher_date,
            AccountingPeriod.end_date >= voucher.voucher_date,
        )
        .order_by(AccountingPeriod.start_date.desc())
        .first()
    )
    if not period:
        raise VoucherValidationError(
            f"无法为凭证日期 {voucher.voucher_date} 找到匹配的会计期间"
        )
    return period.id


def delete_voucher_by_id(
    db: Session,
    *,
    user: User,
    voucher_id: int,
) -> None:
    """
    根据ID删除凭证。

    业务逻辑：
    1. 校验用户账簿权限。
    2. 仅允许删除草稿状态凭证。
    3. 校验期间未结账。
    """
    voucher = get_voucher_by_id(db, voucher_id)
    if not voucher:
        raise VoucherNotFoundError(f"凭证 {voucher_id} 不存在")

    _check_ledger_access(db, user.id, voucher.ledger_id)

    if voucher.status != "draft":
        raise VoucherStateError("只有草稿状态凭证可以删除")

    # 校验期间状态
    period = (
        db.query(AccountingPeriod)
        .filter(
            AccountingPeriod.ledger_id == voucher.ledger_id,
            AccountingPeriod.start_date <= voucher.voucher_date,
            AccountingPeriod.end_date >= voucher.voucher_date,
        )
        .first()
    )
    if period and period.status not in {"open", "reopened"}:
        raise PeriodClosedError(
            f"会计期间 {period.period_code} 已{period.status}，不能删除凭证"
        )

    delete_voucher(db, voucher_id=voucher_id)
