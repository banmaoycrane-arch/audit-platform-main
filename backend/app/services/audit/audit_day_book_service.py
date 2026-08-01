# -*- coding: utf-8 -*-
"""
序时簿导入专用处理服务

模块功能：对审计模式下的序时簿导入数据进行专用处理，包括凭证合并、
          借贷平衡校验、凭证号连续性检测、科目层级解析与 Tag 生成等。

业务场景：审计人员从被审计单位导入序时簿（按行记录的分录明细），
          需要按凭证号合并为完整凭证，并按项目规范将二级及以下明细科目
          转换为 EntryTag，同时关联往来单位。

政策依据：
    - 《中国注册会计师审计准则第1101号》——审计证据的完整性
    - 会计基础工作规范——记账凭证必须借贷平衡
    - 项目"一级科目 + Dimension(Tag)"核心设计思想

输入数据：序时簿 CSV/Excel 文件，每行一条分录，包含 voucher_no 字段
输出结果：序时簿检测报告（DayBookReport），包含凭证完整性评分与问题清单

创建日期：2026-06-18
更新记录：
    2026-06-18  初始版本，实现序时簿导入核心逻辑
    2026-07-03  增加科目层级解析、EntryTag 生成、Counterparty 关联、向量同步
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

logger = logging.getLogger(__name__)

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from app.db.models import (
    AccountingEntry,
    Counterparty,
    EntryTag,
    ExecutionAuditLog,
    ImportJob,
    SourceFile,
    StagingAccountingEntry,
    TagCategory,
    Voucher,
)
from app.services.accounting.period_detection_service import resolve_voucher_period_id
from app.services.shared.data_validator import generate_quality_report
from app.services.accounting.entry_tags_service import build_semantic_text, generate_entry_tags
from app.services.accounting.entry_tag_vector_service import EntryTagVectorService
from app.services.doc_parsing.file_parser_service import (
    ParseResult,
    build_parse_diagnostics,
    parse_structured_accounting_entries,
)
from app.services.doc_parsing.tag_category_service import get_or_create_category
from app.storage.local_storage import resolve_storage_path
from app.services.shared.logic_check_service import (
    BatchCheckReport,
    check_entry_logic,
    generate_batch_report,
)
from app.services.audit.risk_case_library import enhance_entry_with_risk_analysis
from app.services.doc_parsing.import_routing_service import get_import_mode
from app.services.doc_parsing.tagging_service import suggest_tags, suggest_voucher_type
from app.services.doc_parsing.vector_store_service import chunk_hash, chunk_text, safe_vector_store
from app.core.config import get_settings
from uuid import uuid4
from app.db.models import DocumentChunk


# 会计凭证文件类型
ACCOUNTING_FILE_TYPES = {".xlsx", ".xls", ".csv", ".tsv"}


@dataclass
class UnbalancedVoucher:
    """不平衡凭证信息"""

    voucher_no: str
    debit_total: Decimal
    credit_total: Decimal
    difference: Decimal
    entry_count: int
    voucher_date: str | None = None


@dataclass
class DayBookReport:
    """
    序时簿检测报告

    功能描述：汇总序时簿导入后的凭证完整性检测结果
    业务逻辑：
        1. 按 voucher_no 分组统计凭证数量
        2. 检测凭证号是否连续（跳号识别）
        3. 逐凭证校验借贷平衡
        4. 计算完整性评分

    会计口径：
        - 凭证号连续性：基于字符串排序后的自然数序列检测
        - 借贷平衡：借方合计必须等于贷方合计，差异为 0.00
        - 完整性评分：满分 100，跳号与不平衡各按比例扣分
    """

    total_vouchers: int = 0
    total_entries: int = 0
    unbalanced_vouchers: list[UnbalancedVoucher] = field(default_factory=list)
    missing_voucher_nos: list[str] = field(default_factory=list)
    skip_count: int = 0
    unbalanced_count: int = 0
    completeness_score: int = 100
    logic_check: dict[str, Any] | None = None
    quality_check: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_vouchers": self.total_vouchers,
            "total_entries": self.total_entries,
            "unbalanced_vouchers": [v.__dict__ for v in self.unbalanced_vouchers],
            "missing_voucher_nos": self.missing_voucher_nos,
            "skip_count": self.skip_count,
            "unbalanced_count": self.unbalanced_count,
            "completeness_score": self.completeness_score,
        }


@dataclass
class DayBookProcessingResult:
    """序时簿导入处理结果"""

    success: bool
    entries_created: int = 0
    error_message: str | None = None
    report: DayBookReport | None = None
    parse_diagnostics: dict[str, Any] | None = None


def _amount_to_decimal(value: Any) -> Decimal:
    """
    将任意数值类型安全转换为 Decimal。

    会计口径：金额统一使用 Decimal 避免浮点误差。
    """
    if value is None or value == "":
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
    except Exception:
        logger.warning("_amount_to_decimal: failed to convert %r to Decimal, returning 0.00", value, exc_info=True)
        return Decimal("0.00")


def _build_entry_tags_for_import(
    db: Session,
    entry_objects: list[AccountingEntry],
    entry_data_list: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    为批量创建的 AccountingEntry 生成 EntryTag 映射。

    业务逻辑：
        1. 使用 entry_objects 与 entry_data_list 一一对应。
        2. 从 entry_data 的 suggested_tags 提取 Tag 信息。
        3. 为每个 Tag 构建 EntryTag 行，便于 bulk_insert_mappings。

    会计口径：
        - EntryTag 承载一级科目之外的维度信息
        - 保留 source_sub_code 以便与科目层级/COA 缺口映射对照
    """
    # 预加载所有需要的 TagCategory，避免 N+1
    ledger_ids = {entry.ledger_id for entry in entry_objects}
    category_codes = set()
    for entry_data in entry_data_list:
        for tag in entry_data.get("suggested_tags") or []:
            if isinstance(tag, dict) and tag.get("category_code"):
                category_codes.add(tag["category_code"])
    tag_category_map: dict[tuple[int, str], int] = {}
    if ledger_ids and category_codes:
        cats = (
            db.query(TagCategory)
            .filter(
                TagCategory.ledger_id.in_(ledger_ids),
                TagCategory.code.in_(category_codes),
            )
            .all()
        )
        tag_category_map = {(c.ledger_id, c.code): c.id for c in cats}

    tag_mappings: list[dict[str, Any]] = []
    for entry, entry_data in zip(entry_objects, entry_data_list):
        tags = entry_data.get("suggested_tags") or []
        for tag in tags:
            if not isinstance(tag, dict):
                continue
            category_code = tag.get("category_code")
            category_id = None
            if category_code:
                category_id = tag_category_map.get((entry.ledger_id, category_code))

            tag_value = tag.get("tag_value") or tag.get("dimension_value") or ""
            display_name = tag.get("display_name") or tag_value
            source_sub_code = tag.get("source_sub_code")
            tag_mappings.append(
                {
                    "entry_id": entry.id,
                    "category_id": category_id,
                    "category_code": category_code,
                    "tag_type": category_code,
                    "tag_value": tag_value,
                    "display_name": display_name,
                    "source_sub_code": source_sub_code,
                    "tag_metadata": tag.get("tag_metadata") or {},
                }
            )
    return tag_mappings


def _entry_duplicate_key(entry_data: dict[str, Any]) -> tuple[str, ...]:
    """生成单条分录的去重键。包含行号，避免同一凭证内相同借方分录被误删。"""
    return (
        str(entry_data.get("voucher_no") or ""),
        str(entry_data.get("voucher_date") or ""),
        str(entry_data.get("summary") or ""),
        str(entry_data.get("account_code") or ""),
        str(entry_data.get("account_name") or ""),
        str(_amount_to_decimal(entry_data.get("debit_amount", 0))),
        str(_amount_to_decimal(entry_data.get("credit_amount", 0))),
        str(entry_data.get("counterparty") or ""),
        str(entry_data.get("entry_line_no") or "1"),
    )


def build_accounting_entry_duplicate_key(entry_data: dict[str, Any]) -> tuple[str, ...]:
    """公共包装函数：生成单条分录的去重键。"""
    return _entry_duplicate_key(entry_data)


def _entry_rows_to_duplicate_keys(rows: list[Any]) -> set[tuple[str, ...]]:
    return {
        (
            str(row.voucher_no or ""),
            str(row.voucher_date or ""),
            str(row.summary or ""),
            str(row.account_code or ""),
            str(row.account_name or ""),
            str(_amount_to_decimal(row.debit_amount)),
            str(_amount_to_decimal(row.credit_amount)),
            str(row.counterparty or ""),
            str(row.entry_line_no or "1"),
        )
        for row in rows
    }


def _accounting_entry_identity_columns() -> tuple[Any, ...]:
    """用于去重查询的列集合。"""
    return (
        AccountingEntry.voucher_no,
        AccountingEntry.voucher_date,
        AccountingEntry.summary,
        AccountingEntry.account_code,
        AccountingEntry.account_name,
        AccountingEntry.debit_amount,
        AccountingEntry.credit_amount,
        AccountingEntry.counterparty,
        AccountingEntry.entry_line_no,
    )


def _staging_entry_identity_columns() -> tuple[Any, ...]:
    """用于去重查询的 StagingAccountingEntry 列集合。"""
    return (
        StagingAccountingEntry.voucher_no,
        StagingAccountingEntry.voucher_date,
        StagingAccountingEntry.summary,
        StagingAccountingEntry.account_code,
        StagingAccountingEntry.account_name,
        StagingAccountingEntry.debit_amount,
        StagingAccountingEntry.credit_amount,
        StagingAccountingEntry.counterparty,
        StagingAccountingEntry.entry_line_no,
    )


def _existing_entry_duplicate_keys(db: Session, job_id: int) -> set[tuple[str, ...]]:
    """读取当前导入任务已落库分录的去重口径。"""
    existing_rows = (
        db.query(*_accounting_entry_identity_columns())
        .filter(AccountingEntry.import_job_id == job_id)
        .all()
    )
    return _entry_rows_to_duplicate_keys(existing_rows)


def _existing_ledger_entry_duplicate_keys(
    db: Session, ledger_id: int
) -> set[tuple[str, ...]]:
    """读取账簿已落库分录的去重口径，防止同一账簿重复导入时再次插入。"""
    existing_rows = (
        db.query(*_accounting_entry_identity_columns())
        .filter(AccountingEntry.ledger_id == ledger_id)
        .all()
    )
    return _entry_rows_to_duplicate_keys(existing_rows)


def _existing_staging_duplicate_keys(db: Session, job_id: int) -> set[tuple[str, ...]]:
    """读取当前导入任务已存在的 staging 分录去重口径。"""
    existing_rows = (
        db.query(*_staging_entry_identity_columns())
        .filter(StagingAccountingEntry.import_job_id == job_id)
        .all()
    )
    return _entry_rows_to_duplicate_keys(existing_rows)


def _parse_and_validate_day_book(
    db: Session,
    job: ImportJob,
    existing_entry_count: int | None = None,
) -> tuple[
    list[dict[str, Any]],
    DayBookReport,
    BatchCheckReport | None,
    dict[str, Any] | None,
]:
    """
    序时簿解析与校验阶段（不写入任何持久化数据）。

    复用 process_day_book_import 的解析、去重、行号分配、借贷平衡、
    逻辑校验与检测报告生成逻辑，返回原始分录 dict 列表与报告对象。

    返回：
        all_entries: 解析后的分录数据列表（按 voucher_no 已分配 entry_line_no）
        day_book_report: 序时簿检测报告
        logic_report: 逻辑校验报告（可能为 None）
        parse_diagnostics: 当解析无分录时的诊断信息（否则为 None）
    """
    existing_keys = _existing_entry_duplicate_keys(db, job.id)
    if job.ledger_id is not None:
        existing_keys |= _existing_ledger_entry_duplicate_keys(db, job.ledger_id)

    files = db.query(SourceFile).filter(SourceFile.import_job_id == job.id).all()

    all_entries: list[dict[str, Any]] = []
    last_parse_diagnostics: dict[str, Any] | None = None
    total_parsed_entries = 0

    for source_file in files:
        file_type = source_file.file_type.lower()
        if file_type not in {"xlsx", "xls", "csv", "tsv"}:
            continue

        parse_result = parse_structured_accounting_entries(
            resolve_storage_path(source_file.storage_path), db=db
        )
        total_parsed_entries += len(parse_result.entries)
        if not parse_result.entries:
            last_parse_diagnostics = build_parse_diagnostics(parse_result)
        for parsed_entry in parse_result.entries:
            duplicate_key = _entry_duplicate_key(parsed_entry)
            if duplicate_key in existing_keys:
                continue
            existing_keys.add(duplicate_key)
            parsed_entry["source_file_id"] = source_file.id
            all_entries.append(parsed_entry)

    if not all_entries:
        if total_parsed_entries > 0:
            raise _DayBookImportError(
                "解析到的分录均已存在于当前账套/任务中，未新增分录。如需全量重导请更换账套或清理已有分录。",
                parse_diagnostics=last_parse_diagnostics,
            )
        raise _DayBookImportError(
            "未解析到有效分录数据，请检查表头列名是否包含凭证号、日期、摘要、科目、借贷金额",
            parse_diagnostics=last_parse_diagnostics,
        )

    _assign_entry_line_numbers(all_entries)

    entries_for_check: list[dict[str, Any]] = []
    voucher_types: list[str | None] = []

    for entry_data in all_entries:
        class MockEntry:
            def __init__(self, d: dict[str, Any]) -> None:
                self.summary: str = d.get("summary", "")
                self.account_name: str = d.get("account_name", "")
                self.debit_amount: Decimal = d.get("debit_amount", Decimal("0"))
                self.credit_amount: Decimal = d.get("credit_amount", Decimal("0"))
                self.voucher_date: None = None
                self.account_code: str = d.get("account_code", "")

        mock_entry = MockEntry(entry_data)
        voucher_type, _ = suggest_voucher_type(mock_entry)
        voucher_types.append(voucher_type)

        entries_for_check.append({
            "summary": entry_data.get("summary", ""),
            "debit_account": entry_data.get("account_name", ""),
            "credit_account": entry_data.get("account_name", ""),
            "debit_amount": entry_data.get("debit_amount", 0),
            "credit_amount": entry_data.get("credit_amount", 0),
            "voucher_type": voucher_type,
        })

    logic_check_results = []
    for i, (entry_data, voucher_type) in enumerate(zip(entries_for_check, voucher_types)):
        check_result = check_entry_logic(
            entry_index=i,
            summary=entry_data["summary"],
            debit_account=entry_data["debit_account"],
            credit_account=entry_data["credit_account"],
            debit_amount=entry_data["debit_amount"],
            credit_amount=entry_data["credit_amount"],
            voucher_type=voucher_type,
        )
        logic_check_results.append(check_result)

    logic_report = generate_batch_report(logic_check_results)
    day_book_report = _build_day_book_report(all_entries)

    return all_entries, day_book_report, logic_report, None


class _DayBookImportError(Exception):
    """序时簿导入业务错误，用于在解析阶段携带 parse_diagnostics。"""

    def __init__(self, message: str, parse_diagnostics: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.parse_diagnostics = parse_diagnostics


def _existing_ledger_voucher_no_to_id(db: Session, ledger_id: int) -> dict[str, int]:
    """读取账簿已有凭证号到凭证 ID 的映射，避免违反 ledger_id + voucher_no 唯一约束。"""
    rows = (
        db.query(Voucher.voucher_no, Voucher.id)
        .filter(Voucher.ledger_id == ledger_id)
        .all()
    )
    return {row.voucher_no: row.id for row in rows if row.voucher_no}


def _extract_voucher_number(voucher_no: str) -> str:
    """从凭证号中提取数字部分。"""
    digits = ""
    for char in voucher_no:
        if char.isdigit():
            digits += char
    return digits if digits else voucher_no


def _detect_voucher_number_skips(voucher_nos: list[str]) -> list[str]:
    """
    检测凭证号跳号

    功能描述：对凭证号列表排序后，检测是否存在不连续的数字序列
    业务逻辑：
        1. 提取每个凭证号的数字部分
        2. 按数字大小排序
        3. 相邻数字差大于 1 时，判定为跳号
        4. 记录缺失的凭证号（基于第一个凭证号的前缀格式）

    会计口径：
        - 仅检测数字部分连续，前缀（如"记-"）保持一致
        - 非数字凭证号不参与跳号检测

    Args:
        voucher_nos: 凭证号列表

    Returns:
        list[str]: 缺失的凭证号列表（按原格式补全）
    """
    if not voucher_nos:
        return []

    # 提取数字并保留原始映射
    numbered_vouchers: list[tuple[int, str, str]] = []
    for voucher_no in voucher_nos:
        digits = _extract_voucher_number(voucher_no)
        if digits.isdigit():
            numbered_vouchers.append((int(digits), digits, voucher_no))

    if not numbered_vouchers:
        return []

    # 按数字排序
    numbered_vouchers.sort(key=lambda x: x[0])

    # 推断前缀格式（取第一个凭证号中非数字部分）
    first_original = numbered_vouchers[0][2]
    prefix = ""
    for char in first_original:
        if not char.isdigit():
            prefix += char
        else:
            break

    # 检测跳号
    missing: list[str] = []
    for i in range(1, len(numbered_vouchers)):
        prev_num = numbered_vouchers[i - 1][0]
        curr_num = numbered_vouchers[i][0]
        gap = curr_num - prev_num
        if gap > 1:
            # 记录缺失的凭证号
            for missing_num in range(prev_num + 1, curr_num):
                missing_voucher = f"{prefix}{str(missing_num).zfill(len(numbered_vouchers[0][1]))}"
                missing.append(missing_voucher)

    return missing


def _validate_voucher_balance(
    entries: list[dict[str, Any]],
) -> tuple[bool, Decimal, Decimal, Decimal]:
    """
    校验单个凭证的借贷平衡

    功能描述：对同一凭证号下的所有分录，汇总借方和贷方金额并校验是否相等
    业务逻辑：
        1. 遍历该凭证的所有分录
        2. 使用 Decimal 累加借方金额和贷方金额
        3. 比较借方合计与贷方合计

    会计口径：
        - 记账凭证借贷必须平衡，借方合计 = 贷方合计
        - 金额精度统一为 2 位小数

    Args:
        entries: 同一凭证号下的分录列表

    Returns:
        tuple[bool, Decimal, Decimal, Decimal]:
            (是否平衡, 借方合计, 贷方合计, 差异金额)
    """
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")

    for entry in entries:
        debit = _amount_to_decimal(entry.get("debit_amount", 0))
        credit = _amount_to_decimal(entry.get("credit_amount", 0))
        total_debit += debit
        total_credit += credit

    total_debit = total_debit.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
    total_credit = total_credit.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
    difference = (total_debit - total_credit).quantize(
        Decimal("0.00"), rounding=ROUND_HALF_UP
    )

    return total_debit == total_credit, total_debit, total_credit, difference


def _assign_entry_line_numbers(entries: list[dict[str, Any]]) -> None:
    """
    为同一凭证号（parse_group_key）下的分录分配连续 entry_line_no。

    业务场景：续行文件可能跨多个源文件，需要按 voucher_no 全局排序后分配行号。
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for entry in entries:
        key = entry.get("voucher_no") or "__no_voucher__"
        groups.setdefault(key, []).append(entry)

    for group_entries in groups.values():
        for i, entry in enumerate(group_entries, start=1):
            entry["entry_line_no"] = i


def _build_day_book_report(entries: list[dict[str, Any]]) -> DayBookReport:
    """
    构建序时簿检测报告

    功能描述：按凭证号 + 凭证日期分组，逐凭证校验借贷平衡并检测跳号。
    业务场景：同一凭证号在不同日期出现时，视为不同凭证（如跨月补记）。
    """
    voucher_groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for idx, entry in enumerate(entries):
        voucher_no = entry.get("voucher_no") or f"__no_voucher__:{idx}"
        voucher_date = entry.get("voucher_date") or ""
        group_key = (voucher_no, str(voucher_date))
        voucher_groups.setdefault(group_key, []).append(entry)

    unbalanced_vouchers: list[UnbalancedVoucher] = []
    total_vouchers = len(voucher_groups)
    total_entries = len(entries)

    for (voucher_no, voucher_date), group_entries in voucher_groups.items():
        if voucher_no.startswith("__no_voucher__"):
            continue
        is_balanced, debit_total, credit_total, difference = _validate_voucher_balance(
            group_entries
        )
        if not is_balanced:
            unbalanced_vouchers.append(
                UnbalancedVoucher(
                    voucher_no=voucher_no,
                    debit_total=debit_total,
                    credit_total=credit_total,
                    difference=difference,
                    entry_count=len(group_entries),
                    voucher_date=str(group_entries[0].get("voucher_date")),
                )
            )

    valid_voucher_nos = list(
        {v for v, _ in voucher_groups.keys() if not v.startswith("__no_voucher__")}
    )
    missing_voucher_nos = _detect_voucher_number_skips(valid_voucher_nos)

    skip_count = len(missing_voucher_nos)
    unbalanced_count = len(unbalanced_vouchers)

    # 完整性评分：跳号与不平衡各占 50 分
    score = 100
    if total_vouchers > 0:
        score -= int((unbalanced_count / total_vouchers) * 50)
        score -= int((skip_count / total_vouchers) * 50)
    score = max(0, min(100, score))

    return DayBookReport(
        total_vouchers=total_vouchers,
        total_entries=total_entries,
        unbalanced_vouchers=unbalanced_vouchers,
        missing_voucher_nos=missing_voucher_nos,
        skip_count=skip_count,
        unbalanced_count=unbalanced_count,
        completeness_score=score,
    )


def _resolve_counterparty(
    db: Session,
    counterparty_name: str | None,
) -> int | None:
    """
    根据名称匹配或创建 Counterparty。

    业务逻辑：
        1. 空名称直接返回 None。
        2. 按 name 精确匹配现有 Counterparty。
        3. 未匹配时自动创建新记录，默认 role 为 other。

    会计口径：
        导入流程中自动创建的往来单位仅作为临时记录，后续可人工复核修正。

    Args:
        db: 数据库会话
        counterparty_name: 往来单位名称

    Returns:
        Counterparty ID 或 None
    """
    if not counterparty_name:
        return None

    name = counterparty_name.strip()
    if not name:
        return None

    cp = db.query(Counterparty).filter(Counterparty.name == name).first()
    if cp:
        return cp.id

    new_cp = Counterparty(name=name, role="other")
    db.add(new_cp)
    db.flush()
    return new_cp.id


def _resolve_counterparty_bulk(
    db: Session,
    counterparty_names: list[str | None],
) -> dict[str, int | None]:
    """
    批量解析往来单位名称到 ID，避免循环内逐条查询（N+1）。

    策略：
        1. 一次性查询所有已存在的 Counterparty。
        2. 对不存在且非空的名称，批量创建 Counterparty 并 flush 获取 ID。
        3. 返回 name -> id 的映射；空/None 名称映射为 None。

    会计口径：与 _resolve_counterparty 一致，自动创建的往来单位为临时记录。
    """
    # 规范化名称并保留原始顺序
    normalized_names: list[str] = []
    for name in counterparty_names:
        normalized = (name or "").strip()
        normalized_names.append(normalized)

    unique_non_empty = sorted({n for n in normalized_names if n})
    if not unique_non_empty:
        return {n: None for n in normalized_names}

    existing_rows = (
        db.query(Counterparty.id, Counterparty.name)
        .filter(Counterparty.name.in_(unique_non_empty))
        .all()
    )
    name_to_id: dict[str, int | None] = {
        str(row.name): row.id for row in existing_rows if row.name
    }

    missing = [n for n in unique_non_empty if name_to_id.get(n) is None]
    if missing:
        db.bulk_insert_mappings(
            Counterparty,
            [{"name": n, "role": "other"} for n in missing],
        )
        db.flush()
        created_rows = (
            db.query(Counterparty.id, Counterparty.name)
            .filter(Counterparty.name.in_(missing))
            .all()
        )
        for row in created_rows:
            if row.name:
                name_to_id[str(row.name)] = row.id

    return {n: name_to_id.get(n) if n else None for n in normalized_names}


def _ensure_tag_categories(
    db: Session,
    ledger_id: int,
    category_codes: set[str],
) -> dict[str, TagCategory]:
    """
    确保导入所需 TagCategory 存在。

    业务逻辑：
        1. 查询已存在的分类。
        2. 对缺失分类按默认配置自动创建。
    """
    from app.config.tag_category_constants import DEFAULT_CATEGORY_META

    existing = (
        db.query(TagCategory)
        .filter(
            TagCategory.ledger_id == ledger_id,
            TagCategory.code.in_(list(category_codes)),
        )
        .all()
    )
    code_to_category = {cat.code: cat for cat in existing}

    missing_codes = category_codes - set(code_to_category.keys())
    for code in missing_codes:
        meta = DEFAULT_CATEGORY_META.get(code, {"name": code, "description": ""})
        category = TagCategory(
            ledger_id=ledger_id,
            code=code,
            name=meta.get("name", code),
            description=meta.get("description", ""),
        )
        db.add(category)
        code_to_category[code] = category

    if missing_codes:
        db.flush()

    return code_to_category


def _build_semantic_text_for_entries(entries: list[dict[str, Any]]) -> str:
    """
    为待向量化分录构建语义文本。

    业务逻辑：
        1. 汇总所有分录的摘要、科目、借贷方向。
        2. 拼接为可读文本，用于后续向量索引与检索。
    """
    parts: list[str] = []
    for entry in entries:
        summary = entry.get("summary", "")
        account_name = entry.get("account_name", "")
        debit = _amount_to_decimal(entry.get("debit_amount", 0))
        credit = _amount_to_decimal(entry.get("credit_amount", 0))
        direction = "借" if debit > 0 else "贷" if credit > 0 else "平"
        amount = debit if debit > 0 else credit
        parts.append(f"{summary}|{account_name}|{direction}{amount}")
    return "\n".join(parts)


def _vectorize_entries(
    db: Session,
    entries: list[AccountingEntry],
    entry_data_list: list[dict[str, Any]],
    job: ImportJob,
) -> None:
    """
    将导入的分录向量化存储，支持语义检索。

    业务逻辑：
        1. 每批分录生成语义文本并分块。
        2. 使用向量存储服务写入 DocumentChunk。
        3. 失败时记录警告但不阻断主流程。
    """
    if not entries:
        return

    try:
        settings = get_settings()
        vector_enabled = getattr(settings, "VECTOR_STORE_ENABLED", True)
        if not vector_enabled:
            return
    except Exception:
        logger.warning("vector store settings check failed, skipping vector sync", exc_info=True)
        return

    try:
        semantic_text = _build_semantic_text_for_entries(entry_data_list)
        if not semantic_text.strip():
            return

        chunk_id = chunk_hash(semantic_text, prefix="daybook")
        text_chunks = chunk_text(semantic_text)
        for idx, text_chunk in enumerate(text_chunks):
            chunk_uuid = f"{chunk_id}_{idx}"
            safe_vector_store(
                db,
                text=text_chunk,
                chunk_id=chunk_uuid,
                metadata={
                    "import_job_id": str(job.id),
                    "ledger_id": str(job.ledger_id) if job.ledger_id else None,
                    "project_id": str(job.project_id) if job.project_id else None,
                    "chunk_index": idx,
                    "source_type": "day_book",
                    "total_entries": len(entries),
                },
            )

        # 更新或创建 DocumentChunk 记录，便于审计追溯
        document_chunk = DocumentChunk(
            source_id=str(job.id),
            chunk_type="day_book",
            content=semantic_text,
            source_type="day_book",
        )
        db.add(document_chunk)
    except Exception:
        logger.warning("vector sync failed for import job %s, continuing", job.id if job else None, exc_info=True)
        pass


def _persist_entries_from_dicts(
    db: Session,
    job: ImportJob,
    all_entries: list[dict[str, Any]],
    day_book_report: DayBookReport,
    logic_report: BatchCheckReport | None,
    *,
    trace_prefix: str = "process_day_book_import",
) -> int:
    """
    从已解析分录 dict 列表写入正式 Voucher/AccountingEntry/EntryTag/ExecutionAuditLog。

    幂等说明：调用方需保证本 job 没有既有正式分录，或已做去重过滤。
    返回创建的分录数量。
    """
    import uuid

    trace_id = str(uuid.uuid4())
    request_id = str(uuid.uuid4())

    db.add(
        ExecutionAuditLog(
            trace_id=trace_id,
            request_id=request_id,
            service_name="audit_day_book_service",
            tool_name=trace_prefix,
            execution_source="api",
            business_object_type="import_job",
            business_object_id=str(job.id),
            ledger_id=job.ledger_id,
            project_id=job.project_id,
            status="started",
            risk_level="low",
            input_summary={
                "total_vouchers": day_book_report.total_vouchers,
                "total_entries": len(all_entries),
                "source_type": job.source_type,
            },
        )
    )

    existing_voucher_no_to_id = (
        _existing_ledger_voucher_no_to_id(db, job.ledger_id)
        if job.ledger_id is not None
        else {}
    )
    voucher_no_to_id: dict[str, int] = dict(existing_voucher_no_to_id)
    voucher_groups: dict[str, list[dict[str, Any]]] = {}
    for entry_data in all_entries:
        voucher_no = str(entry_data.get("voucher_no") or "").strip()
        if not voucher_no:
            continue
        voucher_groups.setdefault(voucher_no, []).append(entry_data)

    for voucher_no, entries in voucher_groups.items():
        if voucher_no.startswith("__no_voucher__"):
            continue
        if voucher_no in existing_voucher_no_to_id:
            continue

        first_entry = entries[0]
        voucher_date = first_entry.get("voucher_date")
        summary = first_entry.get("summary", "")[:200]

        voucher_debit_total: Decimal = sum(
            Decimal(str(e.get("debit_amount", "0")))
            for e in entries
            if e.get("debit_amount")
        ) or Decimal("0")
        voucher_credit_total: Decimal = sum(
            Decimal(str(e.get("credit_amount", "0")))
            for e in entries
            if e.get("credit_amount")
        ) or Decimal("0")

        voucher = Voucher(
            organization_id=job.organization_id,
            ledger_id=job.ledger_id,
            voucher_no=voucher_no,
            voucher_date=voucher_date,
            summary=summary,
            total_debit=voucher_debit_total,
            total_credit=voucher_credit_total,
            import_job_id=job.id,
            status="draft",
            source_type="import",
        )
        db.add(voucher)

    db.flush()

    for voucher in db.query(Voucher).filter(Voucher.import_job_id == job.id).all():
        voucher_no_to_id[voucher.voucher_no] = voucher.id

    db.add(
        ExecutionAuditLog(
            trace_id=trace_id,
            request_id=request_id,
            service_name="audit_day_book_service",
            tool_name=trace_prefix,
            execution_source="api",
            business_object_type="import_job",
            business_object_id=str(job.id),
            ledger_id=job.ledger_id,
            project_id=job.project_id,
            status="vouchers_created",
            risk_level="low",
            input_summary={"voucher_count": len(voucher_no_to_id)},
        )
    )

    entry_objects: list[AccountingEntry] = []
    counterparty_names = [
        entry_data.get("resolved_counterparty") or entry_data.get("counterparty")
        for entry_data in all_entries
    ]
    counterparty_name_to_id = _resolve_counterparty_bulk(db, counterparty_names)

    for entry_data in all_entries:
        source_file_id = entry_data.get("source_file_id")
        voucher_no = entry_data.get("voucher_no") or ""
        voucher_id = voucher_no_to_id.get(voucher_no)

        counterparty_name = entry_data.get("resolved_counterparty") or entry_data.get("counterparty")
        counterparty_id = counterparty_name_to_id.get(counterparty_name)

        entry = AccountingEntry(
            organization_id=job.organization_id,
            ledger_id=job.ledger_id,
            voucher_id=voucher_id,
            import_job_id=job.id,
            source_file_id=source_file_id,
            entry_source="auto",
            voucher_no=entry_data.get("voucher_no"),
            voucher_date=entry_data.get("voucher_date"),
            summary=entry_data.get("summary", ""),
            account_code=entry_data.get("account_code"),
            account_name=entry_data.get("account_name"),
            resolved_account_code=entry_data.get("resolved_account_code"),
            resolved_account_name=entry_data.get("resolved_account_name"),
            debit_amount=_amount_to_decimal(entry_data.get("debit_amount", 0)),
            credit_amount=_amount_to_decimal(entry_data.get("credit_amount", 0)),
            counterparty=entry_data.get("counterparty"),
            counterparty_id=counterparty_id,
            original_row=entry_data.get("original_row", {}),
            normalized_text=entry_data.get("normalized_text", ""),
            entry_line_no=entry_data.get("entry_line_no", 1),
        )
        entry_objects.append(entry)
        db.add(entry)

    db.flush()
    total_created = len(entry_objects)

    # 确保 TagCategory 存在（旧流程/直接落库入口可能未预先创建）
    if job.ledger_id is not None:
        category_codes: set[str] = set()
        for entry_data in all_entries:
            for tag in entry_data.get("suggested_tags") or []:
                if isinstance(tag, dict) and tag.get("category_code"):
                    category_codes.add(tag["category_code"])
        if category_codes:
            _ensure_tag_categories(db, job.ledger_id, category_codes)

    tag_mappings = _build_entry_tags_for_import(db, entry_objects, all_entries)
    if tag_mappings:
        db.bulk_insert_mappings(EntryTag, tag_mappings)

    db.add(
        ExecutionAuditLog(
            trace_id=trace_id,
            request_id=request_id,
            service_name="audit_day_book_service",
            tool_name=trace_prefix,
            execution_source="api",
            business_object_type="import_job",
            business_object_id=str(job.id),
            ledger_id=job.ledger_id,
            project_id=job.project_id,
            status="entries_created",
            risk_level="low",
            input_summary={
                "entry_count": total_created,
                "tag_count": len(tag_mappings),
            },
        )
    )

    db.commit()

    try:
        vector_service = EntryTagVectorService(db)
        sync_result = vector_service.sync_pending(limit=200)
        db.add(
            ExecutionAuditLog(
                trace_id=trace_id,
                request_id=request_id,
                service_name="audit_day_book_service",
                tool_name=trace_prefix,
                execution_source="api",
                business_object_type="import_job",
                business_object_id=str(job.id),
                ledger_id=job.ledger_id,
                project_id=job.project_id,
                status="vector_synced",
                risk_level="low",
                input_summary={"vector_synced": sync_result},
            )
        )
        db.commit()
    except Exception as exc:
        logger.warning(f"Vector sync failed in {trace_prefix}: {exc}", exc_info=True)

    report = day_book_report
    report.logic_check = asdict(logic_report) if logic_report else None
    report.quality_check = generate_quality_report(all_entries)

    return total_created


def _entry_data_to_staging(
    entry_data: dict[str, Any],
    job: ImportJob,
    counterparty_name_to_id: dict[str, int | None],
) -> dict[str, Any]:
    """将解析后的分录 dict 转换为 StagingAccountingEntry 插入映射。"""
    counterparty_name = entry_data.get("resolved_counterparty") or entry_data.get("counterparty")
    return {
        "import_job_id": job.id,
        "organization_id": job.organization_id,
        "ledger_id": job.ledger_id,
        "project_id": job.project_id,
        "entity_org_id": job.organization_id,
        "import_mode": "A",
        "source_type": job.source_type,
        "voucher_no": entry_data.get("voucher_no"),
        "voucher_date": entry_data.get("voucher_date"),
        "summary": entry_data.get("summary", ""),
        "account_code": entry_data.get("account_code"),
        "account_name": entry_data.get("account_name"),
        "resolved_account_code": entry_data.get("resolved_account_code"),
        "resolved_account_name": entry_data.get("resolved_account_name"),
        "debit_amount": _amount_to_decimal(entry_data.get("debit_amount", 0)),
        "credit_amount": _amount_to_decimal(entry_data.get("credit_amount", 0)),
        "counterparty": entry_data.get("counterparty"),
        "counterparty_id": counterparty_name_to_id.get(counterparty_name),
        "entry_line_no": entry_data.get("entry_line_no", 1),
        "source_file_id": entry_data.get("source_file_id"),
        "original_row": entry_data.get("original_row", {}),
        "normalized_text": entry_data.get("normalized_text", ""),
        "entry_tags_payload": entry_data.get("suggested_tags") or [],
        "review_status": "draft",
    }


def process_day_book_import(db: Session, job: ImportJob) -> DayBookProcessingResult:
    """
    处理序时簿导入任务：直接落库正式 Voucher/AccountingEntry。

    功能描述：
        1. 解析源文件并校验。
        2. 若本 job 已有正式分录，直接返回（幂等）。
        3. 否则写入正式 Voucher/AccountingEntry/EntryTag。

    会计口径：
        - 同凭证号分录按导入顺序分配 entry_line_no
        - 借贷平衡校验使用 Decimal 精确计算
        - 跳号检测基于凭证号数字部分排序
        - 一级科目保留；强制二级科目保留完整层级；其余下级段转 EntryTag

    注意：这是旧流程/内部直接落库入口；preview/confirm 两阶段流程请使用
          preview_day_book_import / confirm_day_book_import。
    """
    try:
        existing_entry_count = (
            db.query(AccountingEntry)
            .filter(AccountingEntry.import_job_id == job.id)
            .count()
        )
        if existing_entry_count > 0:
            return DayBookProcessingResult(
                success=True,
                entries_created=existing_entry_count,
                report=None,
            )

        all_entries, day_book_report, logic_report, parse_diagnostics = _parse_and_validate_day_book(
            db, job, existing_entry_count=0
        )
        total_created = _persist_entries_from_dicts(
            db,
            job,
            all_entries,
            day_book_report,
            logic_report,
            trace_prefix="process_day_book_import",
        )
        day_book_report.logic_check = asdict(logic_report) if logic_report else None
        day_book_report.quality_check = generate_quality_report(all_entries)

        return DayBookProcessingResult(
            success=True,
            entries_created=total_created,
            report=day_book_report,
            parse_diagnostics=parse_diagnostics,
        )
    except _DayBookImportError as exc:
        db.rollback()
        logger.warning("process_day_book_import parse error: %s", exc.message, exc_info=True)
        return DayBookProcessingResult(
            success=False,
            error_message=exc.message,
            parse_diagnostics=exc.parse_diagnostics,
        )
    except Exception as exc:
        db.rollback()
        logger.warning("process_day_book_import failed: %s", exc, exc_info=True)
        return DayBookProcessingResult(success=False, error_message=str(exc))


def preview_day_book_import(db: Session, job: ImportJob) -> DayBookProcessingResult:
    """
    序时簿导入预览：解析源文件，写入 StagingAccountingEntry，不写入正式表。

    业务逻辑：
        1. 若本 job 已有正式 AccountingEntry，直接返回幂等结果。
        2. 复用 _parse_and_validate_day_book 解析并校验。
        3. 对解析结果去重后写入 StagingAccountingEntry；若解析结果均被 ledger
           已有分录去重，则视为无新增 staging，但仍返回报告并将任务置为 preview。
        4. 不写入 Voucher/AccountingEntry。
        5. 返回 preview 报告供前端展示。

    会计口径：预览必须保证“所见即所得”，借贷平衡、跳号等校验与正式导入一致。
    """
    try:
        existing_entry_count = (
            db.query(AccountingEntry)
            .filter(AccountingEntry.import_job_id == job.id)
            .count()
        )
        if existing_entry_count > 0:
            return DayBookProcessingResult(
                success=True,
                entries_created=existing_entry_count,
                report=None,
            )

        all_entries, day_book_report, logic_report, parse_diagnostics = _parse_and_validate_day_book(
            db, job, existing_entry_count=0
        )

        # 去重：避免重复 preview 时插入重复 staging 行
        existing_staging_keys = _existing_staging_duplicate_keys(db, job.id)
        new_entries = [
            e for e in all_entries
            if _entry_duplicate_key(e) not in existing_staging_keys
        ]

        if new_entries:
            counterparty_names = [
                e.get("resolved_counterparty") or e.get("counterparty")
                for e in new_entries
            ]
            counterparty_name_to_id = _resolve_counterparty_bulk(db, counterparty_names)
            staging_mappings = [
                _entry_data_to_staging(e, job, counterparty_name_to_id)
                for e in new_entries
            ]
            db.bulk_insert_mappings(StagingAccountingEntry, staging_mappings)

        day_book_report.logic_check = asdict(logic_report) if logic_report else None
        day_book_report.quality_check = generate_quality_report(all_entries)

        job.status = "preview"
        db.commit()

        return DayBookProcessingResult(
            success=True,
            entries_created=0,
            report=day_book_report,
            parse_diagnostics=parse_diagnostics,
        )
    except _DayBookImportError as exc:
        db.rollback()
        logger.warning("preview_day_book_import parse error: %s", exc.message, exc_info=True)
        # 若解析结果全部被 ledger 已有正式分录去重，属于正常的“无新增可预览”，
        # 仍返回成功并将任务置为 preview，避免前端无法继续确认。
        if "均已存在" in exc.message or "未新增分录" in exc.message:
            try:
                job.status = "preview"
                db.commit()
            except Exception as exc:
                db.rollback()
                logger.warning("preview status update failed for job %s: %s", job.id, exc)
            return DayBookProcessingResult(
                success=True,
                entries_created=0,
                report=None,
                parse_diagnostics=exc.parse_diagnostics,
            )
        return DayBookProcessingResult(
            success=False,
            error_message=exc.message,
            parse_diagnostics=exc.parse_diagnostics,
        )
    except Exception as exc:
        db.rollback()
        logger.warning("preview_day_book_import failed: %s", exc, exc_info=True)
        return DayBookProcessingResult(success=False, error_message=str(exc))


def confirm_day_book_import(
    db: Session,
    job: ImportJob,
    *,
    approved_by_user_id: int | None = None,
) -> DayBookProcessingResult:
    """
    确认序时簿导入：检查 staging 复核状态，从 staging 生成正式凭证和分录。

    业务逻辑：
        1. 检查本 job 是否已有正式 AccountingEntry；若已有则幂等返回。
        2. 加载所有 StagingAccountingEntry，校验整张凭证是否已复核且借贷平衡。
        3. 未全部复核或借贷不平衡时返回 400（由上层 routes_imports 转 HTTPException）。
        4. 将 staging 行转换为正式 Voucher/AccountingEntry/EntryTag。
        5. 回填签章链到 Voucher；删除本 job 的 staging 行；更新 ImportJob 状态。

    会计口径：确认后正式表产生凭证分录，已确认任务不可再次 preview/confirm，需先取消。
    """
    try:
        existing_entry_count = (
            db.query(AccountingEntry)
            .filter(AccountingEntry.import_job_id == job.id)
            .count()
        )
        if existing_entry_count > 0:
            return DayBookProcessingResult(
                success=True,
                entries_created=existing_entry_count,
                report=None,
            )

        from app.services.audit.staging_review_service import (
            group_staging_rows,
            validate_staging_ready_for_confirm,
        )

        staging_rows = (
            db.query(StagingAccountingEntry)
            .filter(StagingAccountingEntry.import_job_id == job.id)
            .all()
        )

        # 幂等重复导入：若 staging 为空但 ledger 已存在相同凭证号的分录，
        # 说明本次导入的数据已全部落库，直接返回成功即可。
        if not staging_rows:
            existing_entries = (
                db.query(AccountingEntry)
                .filter(AccountingEntry.import_job_id == job.id)
                .all()
            )
            if existing_entries:
                return DayBookProcessingResult(
                    success=True,
                    entries_created=len(existing_entries),
                    report=None,
                )

            if job.ledger_id is not None:
                source_voucher_nos: set[str] = set()
                files = db.query(SourceFile).filter(SourceFile.import_job_id == job.id).all()
                for source_file in files:
                    parse_result = parse_structured_accounting_entries(
                        resolve_storage_path(source_file.storage_path), db=db
                    )
                    for entry in parse_result.entries:
                        voucher_no = entry.get("voucher_no")
                        if voucher_no:
                            source_voucher_nos.add(str(voucher_no))
                if source_voucher_nos:
                    existing_ledger_entries = (
                        db.query(AccountingEntry)
                        .filter(
                            AccountingEntry.ledger_id == job.ledger_id,
                            AccountingEntry.voucher_no.in_(list(source_voucher_nos)),
                        )
                        .all()
                    )
                    if existing_ledger_entries:
                        job.status = "confirmed"
                        db.commit()
                        return DayBookProcessingResult(
                            success=True,
                            entries_created=0,
                            report=None,
                        )

            return DayBookProcessingResult(
                success=False,
                error_message="没有可确认的草稿分录，请先上传并解析文件",
            )

        validation_error = validate_staging_ready_for_confirm(staging_rows)
        if validation_error:
            return DayBookProcessingResult(success=False, error_message=validation_error)

        # 将 staging 行按原始结构转为 dict，供 _persist_entries_from_dicts 复用
        all_entries: list[dict[str, Any]] = []
        for row in staging_rows:
            all_entries.append({
                "voucher_no": row.voucher_no,
                "voucher_date": row.voucher_date,
                "summary": row.summary,
                "account_code": row.account_code,
                "account_name": row.account_name,
                "resolved_account_code": row.resolved_account_code,
                "resolved_account_name": row.resolved_account_name,
                "debit_amount": row.debit_amount,
                "credit_amount": row.credit_amount,
                "counterparty": row.counterparty,
                "resolved_counterparty": row.counterparty,
                "source_file_id": row.source_file_id,
                "original_row": row.original_row or {},
                "normalized_text": row.normalized_text or "",
                "entry_line_no": row.entry_line_no,
                "suggested_tags": row.entry_tags_payload or [],
            })

        _assign_entry_line_numbers(all_entries)
        day_book_report = _build_day_book_report(all_entries)
        logic_report = None

        total_created = _persist_entries_from_dicts(
            db,
            job,
            all_entries,
            day_book_report,
            logic_report,
            trace_prefix="confirm_day_book_import",
        )

        # 回填签章链
        if job.ledger_id is not None:
            from app.services.audit.voucher_signature_service import (
                signature_from_staging_group,
                stamp_voucher_signatures,
            )

            groups = group_staging_rows(staging_rows)
            voucher_no_to_voucher = {
                v.voucher_no: v
                for v in db.query(Voucher).filter(Voucher.import_job_id == job.id).all()
            }
            for _key, rows in groups.items():
                if not rows:
                    continue
                voucher_no = rows[0].voucher_no
                if not voucher_no:
                    continue
                voucher = voucher_no_to_voucher.get(voucher_no)
                if not voucher:
                    continue
                sig = signature_from_staging_group(rows)
                stamp_voucher_signatures(
                    voucher,
                    source_preparer_name=sig.get("source_preparer_name"),
                    cross_reviewed_by_user_id=sig.get("cross_reviewed_by_user_id"),
                    cross_reviewed_at=sig.get("cross_reviewed_at"),
                    approved_by_user_id=approved_by_user_id,
                    approved_at=None,
                )
            db.commit()

        # 删除本 job 的 staging 行
        db.query(StagingAccountingEntry).filter(
            StagingAccountingEntry.import_job_id == job.id
        ).delete(synchronize_session=False)

        job.status = "confirmed"
        db.commit()

        return DayBookProcessingResult(
            success=True,
            entries_created=total_created,
            report=day_book_report,
        )
    except Exception as exc:
        db.rollback()
        logger.warning("confirm_day_book_import failed: %s", exc, exc_info=True)
        return DayBookProcessingResult(success=False, error_message=str(exc))


def cancel_day_book_import(db: Session, job: ImportJob) -> None:
    """
    取消序时簿导入：清理与该任务关联的草稿和正式数据，并将任务置为 cancelled。

    业务逻辑：
        1. 删除 StagingAccountingEntry 草稿行。
        2. 删除本 job 已写入的 Voucher（其级联关系会自动删除 AccountingEntry）。
        3. 更新 ImportJob.status = "cancelled"。

    会计口径：取消意味着放弃本次导入，所有中间产物必须清理，避免重复或脏数据。
    """
    try:
        db.query(StagingAccountingEntry).filter(
            StagingAccountingEntry.import_job_id == job.id
        ).delete(synchronize_session=False)
        db.query(Voucher).filter(Voucher.import_job_id == job.id).delete(
            synchronize_session=False
        )
        job.status = "cancelled"
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("cancel_day_book_import failed for job %s", job.id, exc_info=True)
        raise


# 在模块末尾初始化 logger
# (logger 已在模块顶部创建)
