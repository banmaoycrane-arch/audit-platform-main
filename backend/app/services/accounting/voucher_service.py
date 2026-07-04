from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, AccountingPeriod, EntryTag, Voucher
from app.services.accounting.entry_tag_service import create_entry_tag
from app.services.accounting.entry_tag_rules_engine import apply_auto_tags_to_voucher_lines
from app.services.shared.transaction_service import transaction_with_retry


class VoucherValidationError(Exception):
    """凭证校验失败异常。"""
    pass


class VoucherBalanceError(VoucherValidationError):
    """凭证借贷不平衡异常。"""
    pass


class VoucherNotFoundError(Exception):
    """凭证不存在异常。"""
    pass


class VoucherStateError(Exception):
    """凭证状态不允许操作异常。"""
    pass


class VoucherStatus:
    """凭证状态常量。"""
    DRAFT = "draft"
    VERIFIED = "verified"
    POSTED = "posted"
    CANCELLED = "cancelled"


class VoucherSourceType:
    """凭证来源类型常量。"""
    MANUAL = "manual"
    IMPORT = "import"
    AI_GENERATED = "ai_generated"
    PERIOD_CLOSE = "period_close"
    SYSTEM = "system"


class VoucherEntryLine:
    """凭证分录行数据对象。"""
    def __init__(
        self,
        account_code: str,
        account_name: Optional[str] = None,
        summary: Optional[str] = None,
        debit_amount: Decimal = Decimal("0.00"),
        credit_amount: Decimal = Decimal("0.00"),
        counterparty: Optional[str] = None,
        counterparty_id: Optional[int] = None,
        source_file_id: Optional[int] = None,
        original_row: Optional[Dict[str, Any]] = None,
        normalized_text: Optional[str] = None,
        entity_id: Optional[int] = None,
        original_entity_name: Optional[str] = None,
        tags: Optional[List[Dict[str, Any]]] = None,
    ):
        self.account_code = account_code
        self.account_name = account_name
        self.summary = summary
        self.debit_amount = debit_amount
        self.credit_amount = credit_amount
        self.counterparty = counterparty
        self.counterparty_id = counterparty_id
        self.source_file_id = source_file_id
        self.original_row = original_row or {}
        self.normalized_text = normalized_text or ""
        self.entity_id = entity_id
        self.original_entity_name = original_entity_name
        self.tags = tags or []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_code": self.account_code,
            "account_name": self.account_name,
            "summary": self.summary,
            "debit_amount": self.debit_amount,
            "credit_amount": self.credit_amount,
            "counterparty": self.counterparty,
            "counterparty_id": self.counterparty_id,
            "source_file_id": self.source_file_id,
            "original_row": self.original_row,
            "normalized_text": self.normalized_text,
            "entity_id": self.entity_id,
            "original_entity_name": self.original_entity_name,
        }


def _validate_amount(line: VoucherEntryLine, index: int) -> None:
    """校验单行金额。"""
    debit = line.debit_amount or Decimal("0.00")
    credit = line.credit_amount or Decimal("0.00")

    if debit < 0 or credit < 0:
        raise VoucherValidationError(f"第 {index} 行借方或贷方金额不能为负数")

    if debit > 0 and credit > 0:
        raise VoucherValidationError(f"第 {index} 行不能同时填写借方和贷方金额")

    if debit == 0 and credit == 0:
        raise VoucherValidationError(f"第 {index} 行至少填写借方或贷方金额")


def _validate_account_code(line: VoucherEntryLine, index: int) -> None:
    """校验科目代码。"""
    if not str(line.account_code or "").strip():
        raise VoucherValidationError(f"第 {index} 行科目代码不能为空")


def validate_voucher_balance(
    voucher_no: str,
    voucher_date: date,
    lines: List[VoucherEntryLine],
    *,
    allow_zero: bool = False,
) -> tuple[Decimal, Decimal]:
    """
    校验凭证借贷是否平衡。

    返回 (total_debit, total_credit)。
    不平衡时抛出 VoucherBalanceError。
    """
    if not lines and not allow_zero:
        raise VoucherValidationError(f"凭证 {voucher_no} 分录行不能为空")

    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")

    for index, line in enumerate(lines, start=1):
        _validate_account_code(line, index)
        _validate_amount(line, index)
        total_debit += line.debit_amount or Decimal("0.00")
        total_credit += line.credit_amount or Decimal("0.00")

    if total_debit != total_credit:
        raise VoucherBalanceError(
            f"凭证 {voucher_no} 借贷不平衡：借方合计 {total_debit}，贷方合计 {total_credit}"
        )

    return total_debit, total_credit


def create_voucher(
    db: Session,
    *,
    ledger_id: int,
    organization_id: int,
    period_id: Optional[int] = None,
    voucher_no: str,
    voucher_date: date,
    summary: Optional[str] = None,
    lines: List[VoucherEntryLine],
    source_type: str = VoucherSourceType.MANUAL,
    source_id: Optional[int] = None,
    import_job_id: Optional[int] = None,
    created_by: Optional[int] = None,
    status: str = VoucherStatus.DRAFT,
    auto_commit: bool = True,
) -> Voucher:
    """
    统一凭证创建入口。

    事务边界说明：
        本函数内部执行以下操作：
        1. 规则引擎自动为分录行生成标签建议（apply_auto_tags_to_voucher_lines）
        2. 校验借贷平衡（validate_voucher_balance）
        3. 创建 Voucher 主记录
        4. 创建 AccountingEntry 分录行（含 flush 获取 entry.id）
        5. 创建 EntryTag 分录标签（含 TagHistory 历史记录）

        事务控制由 auto_commit 参数决定：
        - auto_commit=True（默认）：函数内部管理事务，成功时提交，失败时回滚。
                                    对数据库瞬时错误进行最多 3 次指数退避重试。
        - auto_commit=False：函数不做 commit/rollback，由调用方管理事务边界。
                             适用于需要在同一事务内执行多个凭证创建或其他操作的场景。

    参数说明：
        ledger_id: 账簿 ID，非空
        organization_id: 组织 ID，非空
        period_id: 会计期间 ID
        voucher_no: 凭证号，非空
        voucher_date: 凭证日期
        summary: 凭证摘要
        lines: 分录行列表，不能为空
        source_type: 凭证来源类型（manual/import/ai_generated/period_close/system）
        source_id: 来源 ID（如 import_job_id 或 period_id）
        import_job_id: 导入任务 ID
        created_by: 创建人 ID
        status: 凭证状态（draft/verified/posted/cancelled）
        auto_commit: 是否自动提交事务，默认 True

    返回：
        创建成功的 Voucher 对象（已刷新）

    异常：
        VoucherValidationError: 参数校验失败
        VoucherBalanceError: 借贷不平衡
        TransactionError: 事务执行失败（已自动回滚）
    """
    def _execute() -> Voucher:
        voucher_no_val = str(voucher_no or "").strip()
        if not voucher_no_val:
            raise VoucherValidationError("凭证号不能为空")

        if not organization_id:
            raise VoucherValidationError("组织 ID 不能为空")

        # 自动为分录行生成标签建议
        apply_auto_tags_to_voucher_lines(db, ledger_id, lines)

        # 校验借贷平衡
        total_debit, total_credit = validate_voucher_balance(
            voucher_no_val, voucher_date, lines
        )

        # 创建 Voucher 主记录
        voucher = Voucher(
            ledger_id=ledger_id,
            organization_id=organization_id,
            period_id=period_id,
            voucher_no=voucher_no_val,
            voucher_date=voucher_date,
            summary=summary or "",
            source_type=source_type,
            source_id=source_id,
            import_job_id=import_job_id,
            status=status,
            total_debit=total_debit,
            total_credit=total_credit,
            created_by=created_by,
        )
        db.add(voucher)
        db.flush()  # 获取 voucher.id

        # 创建分录行及标签
        for line_no, line in enumerate(lines, start=1):
            entry = AccountingEntry(
                voucher_id=voucher.id,
                ledger_id=ledger_id,
                organization_id=organization_id,
                import_job_id=import_job_id,
                voucher_no=voucher_no_val,
                voucher_date=voucher_date,
                summary=line.summary or summary or "",
                account_code=line.account_code,
                account_name=line.account_name or "",
                debit_amount=line.debit_amount or Decimal("0.00"),
                credit_amount=line.credit_amount or Decimal("0.00"),
                counterparty=line.counterparty,
                counterparty_id=line.counterparty_id,
                source_file_id=line.source_file_id,
                original_row=line.original_row or {},
                normalized_text=line.normalized_text or "",
                entry_line_no=line_no,
                entity_id=line.entity_id,
                original_entity_name=line.original_entity_name,
                entry_source="manual" if source_type == VoucherSourceType.MANUAL else "auto",
                review_status="draft",
                post_status="draft",
            )
            db.add(entry)
            db.flush()

            # 创建分录标签
            for tag in line.tags or []:
                tag_value = tag.get("tag_value") or tag.get("tag_name") or ""
                if not tag_value:
                    continue

                category_code = tag.get("category_code") or tag.get("tag_type") or "legacy"
                display_name = tag.get("display_name") or tag_value
                weight = float(tag.get("weight", 1.0))
                confidence = float(tag.get("confidence", 0.8))
                value_id = tag.get("value_id")
                reviewed_by_user = tag.get("reviewed_by_user", True)

                try:
                    create_entry_tag(
                        db,
                        entry_id=entry.id,
                        ledger_id=ledger_id,
                        category_code=category_code,
                        tag_value=tag_value,
                        display_name=display_name,
                        weight=weight,
                        value_id=value_id,
                        tag_source=tag.get("tag_source") or "rule",
                        confidence=confidence,
                        reviewed_by_user=reviewed_by_user,
                    )
                except ValueError:
                    db.add(
                        EntryTag(
                            entry_id=entry.id,
                            ledger_id=ledger_id,
                            tag_name=tag_value,
                            tag_type=category_code,
                            tag_value=tag_value,
                            tag_value_normalized=tag_value.strip().lower(),
                            display_name=display_name,
                            weight=weight,
                            tag_source=tag.get("tag_source") or "rule",
                            confidence=confidence,
                            vector_pending=True,
                            reviewed_by_user=reviewed_by_user,
                        )
                    )

        db.refresh(voucher)
        return voucher

    if auto_commit:
        from sqlalchemy.exc import OperationalError, TimeoutError
        from tenacity import retry, stop_after_attempt, wait_exponential

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=lambda r: isinstance(r.outcome.exception(), (OperationalError, TimeoutError)),
        )
        def _execute_with_retry() -> Voucher:
            try:
                voucher = _execute()
                db.commit()
                return voucher
            except (OperationalError, TimeoutError):
                db.rollback()
                raise
            except (VoucherBalanceError, VoucherValidationError):
                db.rollback()
                raise
            except Exception as e:
                db.rollback()
                from app.services.shared.transaction_service import TransactionError
                raise TransactionError(f"凭证创建事务失败：{e}") from e

        return _execute_with_retry()
    else:
        return _execute()


def create_vouchers_from_drafts(
    db: Session,
    *,
    ledger_id: int,
    organization_id: int,
    drafts: List[Dict[str, Any]],
    source_type: str = VoucherSourceType.MANUAL,
    source_id: Optional[int] = None,
    import_job_id: Optional[int] = None,
    created_by: Optional[int] = None,
    status: str = VoucherStatus.DRAFT,
    auto_commit: bool = True,
) -> List[Voucher]:
    """
    从 draft 字典列表批量创建凭证。

    事务边界说明：
        本函数内部批量创建凭证，事务控制由 auto_commit 参数决定：
        - auto_commit=True（默认）：所有凭证在同一事务内提交，任意一张失败全部回滚。
                                    对数据库瞬时错误进行最多 3 次指数退避重试。
        - auto_commit=False：函数不做 commit/rollback，由调用方管理事务边界。

    参数说明：
        draft 格式：每个字典包含 voucher_no, voucher_date, summary, lines(列表)。
        auto_commit: 是否自动提交事务，默认 True

    返回：
        创建成功的 Voucher 对象列表（已刷新）

    异常：
        VoucherValidationError: 参数校验失败
        VoucherBalanceError: 借贷不平衡
        TransactionError: 事务执行失败（已自动回滚）
    """
    def _execute() -> List[Voucher]:
        groups: Dict[str, Dict[str, Any]] = {}
        for draft in drafts:
            vn = str(draft.get("voucher_no") or "").strip()
            if not vn:
                raise VoucherValidationError("draft 中缺少 voucher_no")
            if vn not in groups:
                groups[vn] = {
                    "voucher_date": draft.get("voucher_date"),
                    "summary": draft.get("summary"),
                    "period_id": draft.get("period_id"),
                    "lines": [],
                }
            groups[vn]["lines"].append(draft)

        vouchers = []
        for voucher_no, group in groups.items():
            voucher_date = group["voucher_date"]
            if isinstance(voucher_date, str):
                voucher_date = date.fromisoformat(voucher_date)
            if not isinstance(voucher_date, date):
                raise VoucherValidationError(f"凭证 {voucher_no} 日期格式不正确")

            # 推断或校验会计期间
            period_id = group.get("period_id")
            if not period_id:
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
                    raise VoucherValidationError(
                        f"凭证 {voucher_no} 日期 {voucher_date} 未找到匹配的会计期间"
                    )
                period_id = period.id

            lines = []
            for item in group["lines"]:
                lines.append(
                    VoucherEntryLine(
                        account_code=item.get("account_code"),
                        account_name=item.get("account_name"),
                        summary=item.get("summary"),
                        debit_amount=Decimal(str(item.get("debit_amount") or 0)),
                        credit_amount=Decimal(str(item.get("credit_amount") or 0)),
                        counterparty=item.get("counterparty"),
                        counterparty_id=item.get("counterparty_id"),
                        source_file_id=item.get("source_file_id"),
                        original_row=item.get("original_row"),
                        normalized_text=item.get("normalized_text"),
                        entity_id=item.get("entity_id"),
                        original_entity_name=item.get("original_entity_name"),
                    )
                )

            voucher = create_voucher(
                db,
                ledger_id=ledger_id,
                organization_id=organization_id,
                period_id=period_id,
                voucher_no=voucher_no,
                voucher_date=voucher_date,
                summary=group["summary"],
                lines=lines,
                source_type=source_type,
                source_id=source_id,
                import_job_id=import_job_id,
                created_by=created_by,
                status=status,
                auto_commit=False,
            )
            vouchers.append(voucher)
        return vouchers

    if auto_commit:
        from sqlalchemy.exc import OperationalError, TimeoutError
        from tenacity import retry, stop_after_attempt, wait_exponential

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=lambda r: isinstance(r.outcome.exception(), (OperationalError, TimeoutError)),
        )
        def _execute_with_retry() -> List[Voucher]:
            try:
                vouchers = _execute()
                db.commit()
                return vouchers
            except (OperationalError, TimeoutError):
                db.rollback()
                raise
            except Exception as e:
                db.rollback()
                from app.services.shared.transaction_service import TransactionError
                raise TransactionError(f"批量凭证创建事务失败：{e}") from e

        return _execute_with_retry()
    else:
        return _execute()


def get_voucher_by_id(db: Session, voucher_id: int) -> Optional[Voucher]:
    """根据 ID 获取凭证。"""
    return db.get(Voucher, voucher_id)


def get_voucher_by_no(
    db: Session, *, ledger_id: int, voucher_no: str
) -> Optional[Voucher]:
    """根据凭证号获取凭证。"""
    return (
        db.query(Voucher)
        .filter(Voucher.ledger_id == ledger_id, Voucher.voucher_no == voucher_no)
        .first()
    )


def list_vouchers(
    db: Session,
    *,
    ledger_id: int,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[List[Voucher], int]:
    """查询凭证列表。"""
    query = db.query(Voucher).filter(Voucher.ledger_id == ledger_id)
    if status:
        query = query.filter(Voucher.status == status)
    total = query.count()
    items = query.order_by(Voucher.voucher_date.desc(), Voucher.id.desc()).offset(offset).limit(limit).all()
    return items, total


def get_voucher_lines(db: Session, voucher_id: int) -> List[AccountingEntry]:
    """获取凭证的所有分录行。"""
    return (
        db.query(AccountingEntry)
        .filter(AccountingEntry.voucher_id == voucher_id)
        .order_by(AccountingEntry.entry_line_no.asc())
        .all()
    )


def update_voucher_status(
    db: Session,
    *,
    voucher_id: int,
    status: str,
    posted_by: Optional[int] = None,
    auto_commit: bool = True,
) -> Voucher:
    """
    更新凭证状态。

    事务边界说明：
        本函数同时更新 Voucher 主记录和关联的 AccountingEntry 分录行状态，
        事务控制由 auto_commit 参数决定：
        - auto_commit=True（默认）：函数内部管理事务，成功时提交，失败时回滚。
                                    对数据库瞬时错误进行最多 3 次指数退避重试。
        - auto_commit=False：函数不做 commit/rollback，由调用方管理事务边界。

    参数说明：
        voucher_id: 凭证 ID
        status: 目标状态（draft/verified/posted/cancelled）
        posted_by: 过账人 ID（仅 status=posted 时有效）
        auto_commit: 是否自动提交事务，默认 True

    返回：
        更新后的 Voucher 对象（已刷新）

    异常：
        VoucherNotFoundError: 凭证不存在
        VoucherStateError: 凭证状态不允许操作
        TransactionError: 事务执行失败（已自动回滚）
    """
    def _execute() -> Voucher:
        voucher = db.get(Voucher, voucher_id)
        if not voucher:
            raise VoucherNotFoundError(f"凭证 {voucher_id} 不存在")

        if voucher.status == VoucherStatus.CANCELLED:
            raise VoucherStateError("已取消凭证不能修改状态")

        voucher.status = status
        voucher.updated_at = datetime.now(timezone.utc)

        if status == VoucherStatus.POSTED:
            voucher.posted_at = datetime.now(timezone.utc)
            voucher.posted_by = posted_by

        lines = get_voucher_lines(db, voucher_id)
        for line in lines:
            line.review_status = status
            line.post_status = status
            if status == VoucherStatus.POSTED:
                line.posted_at = datetime.now(timezone.utc)
                line.posted_by = posted_by

        db.flush()
        db.refresh(voucher)
        return voucher

    if auto_commit:
        from sqlalchemy.exc import OperationalError, TimeoutError
        from tenacity import retry, stop_after_attempt, wait_exponential

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=lambda r: isinstance(r.outcome.exception(), (OperationalError, TimeoutError)),
        )
        def _execute_with_retry() -> Voucher:
            try:
                voucher = _execute()
                db.commit()
                return voucher
            except (OperationalError, TimeoutError):
                db.rollback()
                raise
            except Exception as e:
                db.rollback()
                from app.services.shared.transaction_service import TransactionError
                raise TransactionError(f"凭证状态更新事务失败：{e}") from e

        return _execute_with_retry()
    else:
        return _execute()


def delete_voucher(
    db: Session,
    *,
    voucher_id: int,
    auto_commit: bool = True,
) -> None:
    """
    删除凭证及其所有分录行。

    事务边界说明：
        本函数级联删除 Voucher、AccountingEntry、EntryTag，
        事务控制由 auto_commit 参数决定：
        - auto_commit=True（默认）：函数内部管理事务，成功时提交，失败时回滚。
                                    对数据库瞬时错误进行最多 3 次指数退避重试。
        - auto_commit=False：函数不做 commit/rollback，由调用方管理事务边界。

    参数说明：
        voucher_id: 凭证 ID
        auto_commit: 是否自动提交事务，默认 True

    异常：
        VoucherNotFoundError: 凭证不存在
        VoucherStateError: 已过账凭证不能删除
        TransactionError: 事务执行失败（已自动回滚）
    """
    def _execute() -> None:
        voucher = db.get(Voucher, voucher_id)
        if not voucher:
            raise VoucherNotFoundError(f"凭证 {voucher_id} 不存在")

        if voucher.status == VoucherStatus.POSTED:
            raise VoucherStateError("已过账凭证不能删除")

        db.query(EntryTag).filter(EntryTag.entry_id.in_(
            db.query(AccountingEntry.id).filter(AccountingEntry.voucher_id == voucher_id)
        )).delete(synchronize_session=False)

        db.query(AccountingEntry).filter(AccountingEntry.voucher_id == voucher_id).delete()

        db.delete(voucher)

    if auto_commit:
        from sqlalchemy.exc import OperationalError, TimeoutError
        from tenacity import retry, stop_after_attempt, wait_exponential

        @retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=lambda r: isinstance(r.outcome.exception(), (OperationalError, TimeoutError)),
        )
        def _execute_with_retry() -> None:
            try:
                _execute()
                db.commit()
            except (OperationalError, TimeoutError):
                db.rollback()
                raise
            except (VoucherNotFoundError, VoucherStateError):
                db.rollback()
                raise
            except Exception as e:
                db.rollback()
                from app.services.shared.transaction_service import TransactionError
                raise TransactionError(f"凭证删除事务失败：{e}") from e

        _execute_with_retry()
    else:
        _execute()
