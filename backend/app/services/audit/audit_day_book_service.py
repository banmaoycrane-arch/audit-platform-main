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

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
    total_vouchers: int          # 凭证总数（按 voucher_no 分组）
    total_entries: int           # 分录总行数
    skip_count: int              # 跳号数量（缺失的凭证号个数）
    unbalanced_count: int        # 不平衡凭证数量
    completeness_score: float    # 完整性评分（0-100）
    missing_voucher_nos: list[str] = field(default_factory=list)      # 缺失的凭证号列表
    unbalanced_vouchers: list[UnbalancedVoucher] = field(default_factory=list)  # 不平衡凭证列表


@dataclass
class DayBookProcessingResult:
    """序时簿处理结果"""
    success: bool
    entries_created: int = 0
    report: DayBookReport | None = None
    error_message: str | None = None
    parse_diagnostics: dict[str, Any] | None = None


def _amount_to_decimal(value: Any) -> Decimal:
    """
    将金额转换为 Decimal 类型

    功能描述：统一金额数据类型，避免浮点误差
    会计口径：保留 2 位小数，四舍五入规则 ROUND_HALF_UP

    Args:
        value: 输入金额（float, int, str, Decimal 均可）

    Returns:
        Decimal: 标准化后的金额，精度 0.00
    """
    if value is None:
        return Decimal("0.00")
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
    try:
        return Decimal(str(value)).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def _extract_voucher_number(voucher_no: str) -> str:
    """
    提取凭证号中的数字部分

    功能描述：用于凭证号排序和连续性检测
    业务逻辑：将 "记-001" 提取为 "001"，便于数字排序

    Args:
        voucher_no: 原始凭证号字符串

    Returns:
        str: 提取后的数字字符串，若无数字则返回原字符串
    """
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
    difference = (total_debit - total_credit).quantize(Decimal("0.00"), rounding=ROUND_HALF_UP)

    is_balanced = difference == Decimal("0.00")
    return is_balanced, total_debit, total_credit, difference


def _group_entries_for_day_book_report(
    all_entries: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """按 parse_group_key（凭证号+日期+顺序）分组，避免续行解析错误导致整表合并。"""
    from app.services.doc_parsing.voucher_no_resolution import entry_parse_group_key

    groups: dict[str, list[dict[str, Any]]] = {}
    for idx, entry_data in enumerate(all_entries):
        group_key = entry_parse_group_key(entry_data, idx)
        groups.setdefault(group_key, []).append(entry_data)
    return groups


def _assign_entry_line_numbers(all_entries: list[dict[str, Any]]) -> None:
    from app.services.doc_parsing.voucher_no_resolution import assign_parse_group_keys

    if any(entry.get("parse_group_key") for entry in all_entries):
        line_counter: dict[str, int] = {}
        for entry in all_entries:
            group_key = str(entry.get("parse_group_key") or "")
            line_counter[group_key] = line_counter.get(group_key, 0) + 1
            entry["entry_line_no"] = line_counter[group_key]
        return
    assign_parse_group_keys(all_entries)


def _build_day_book_report(all_entries: list[dict[str, Any]]) -> DayBookReport:
    voucher_groups = _group_entries_for_day_book_report(all_entries)

    unbalanced_vouchers: list[UnbalancedVoucher] = []
    for group_key, entries in voucher_groups.items():
        if group_key.startswith("__no_voucher__") or group_key.startswith("__seq_"):
            continue
        is_balanced, debit_total, credit_total, difference = _validate_voucher_balance(entries)
        if not is_balanced:
            first = entries[0]
            voucher_no = first.get("voucher_no") or group_key.split("|", 1)[0]
            voucher_date = first.get("voucher_date")
            date_text = voucher_date.isoformat() if hasattr(voucher_date, "isoformat") else (
                str(voucher_date) if voucher_date else None
            )
            unbalanced_vouchers.append(
                UnbalancedVoucher(
                    voucher_no=voucher_no,
                    voucher_date=date_text,
                    debit_total=debit_total,
                    credit_total=credit_total,
                    difference=difference,
                    entry_count=len(entries),
                )
            )

    voucher_nos_for_skip = [
        entries[0].get("voucher_no")
        for entries in voucher_groups.values()
        if entries and entries[0].get("voucher_no") and not str(entries[0].get("voucher_no")).startswith("__")
    ]
    missing_voucher_nos = _detect_voucher_number_skips([v for v in voucher_nos_for_skip if v])
    total_vouchers = len(voucher_groups)
    skip_count = len(missing_voucher_nos)
    unbalanced_count = len(unbalanced_vouchers)
    completeness_score = 100.0
    if total_vouchers > 0:
        skip_penalty = min(skip_count * 2, 20)
        balance_penalty = min(unbalanced_count * 5, 30)
        completeness_score = max(0.0, 100.0 - skip_penalty - balance_penalty)

    return DayBookReport(
        total_vouchers=total_vouchers,
        total_entries=len(all_entries),
        skip_count=skip_count,
        unbalanced_count=unbalanced_count,
        completeness_score=round(completeness_score, 2),
        missing_voucher_nos=missing_voucher_nos,
        unbalanced_vouchers=unbalanced_vouchers,
    )


def _index_text(db: Session, organization_id: int, source_type: str, source_id: int, text: str, payload: dict[str, Any]) -> None:
    """索引文本到向量存储（复用 import_service 中的逻辑）"""
    store = safe_vector_store()
    for chunk in chunk_text(text):
        point_id = uuid4().hex
        digest = chunk_hash(chunk)
        db.add(
            DocumentChunk(
                organization_id=organization_id,
                source_type=source_type,
                source_id=source_id,
                chunk_text=chunk,
                chunk_hash=digest,
                vector_collection=get_settings().qdrant_collection,
                vector_point_id=point_id,
            )
        )
        if store:
            try:
                store.upsert_text(point_id, chunk, payload | {"source_type": source_type, "source_id": source_id, "chunk_hash": digest})
            except Exception:
                pass


def _entry_duplicate_key(entry_data: dict[str, Any]) -> tuple[str, ...]:
    """生成分录去重口径，防止同一任务重复解析、重复上传同一序时簿。

    须包含凭证内行号：同一凭证可出现多笔相同科目/摘要/金额的借方或贷方分录。
    """
    voucher_date = entry_data.get("voucher_date")
    voucher_date_text = voucher_date.isoformat() if voucher_date and hasattr(voucher_date, "isoformat") else str(voucher_date or "")
    return (
        str(entry_data.get("voucher_no") or "").strip(),
        voucher_date_text,
        str(entry_data.get("parse_group_key") or "").strip(),
        str(entry_data.get("entry_line_no") or "").strip(),
        str(entry_data.get("summary") or "").strip(),
        str(entry_data.get("account_code") or "").strip(),
        str(entry_data.get("account_name") or "").strip(),
        str(_amount_to_decimal(entry_data.get("debit_amount", 0))),
        str(_amount_to_decimal(entry_data.get("credit_amount", 0))),
        str(entry_data.get("counterparty") or "").strip(),
    )


def build_accounting_entry_duplicate_key(entry_data: dict[str, Any]) -> tuple[str, ...]:
    """供其他导入链路复用的分录去重口径。"""
    return _entry_duplicate_key(entry_data)


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
    categories = {cat.code: cat for cat in existing}

    # 默认分类名称映射（自定义维度可在维度分类页扩展，code 使用 snake_case）
    default_meta: dict[str, dict[str, Any]] = dict(DEFAULT_CATEGORY_META)

    for code in category_codes:
        if code in categories:
            continue
        meta = default_meta.get(code, {})
        category = get_or_create_category(
            db,
            ledger_id=ledger_id,
            code=code,
            name=meta.get("name", code),
            value_type=meta.get("value_type", "text"),
            source_table=meta.get("source_table"),
            description=meta.get("description"),
            is_system=True,
        )
        categories[code] = category

    return categories


def _build_entry_tags_for_import(
    db: Session,
    entries: list[AccountingEntry],
    entry_data_list: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    为导入的分录批量构建 EntryTag。

    业务逻辑：
        1. 收集所有需要的 TagCategory 并确保存在。
        2. 为每条分录的 suggested_tags 生成 EntryTag 记录。
        3. 默认标记 vector_pending=True，等待后续向量同步。
    """
    category_codes: set[str] = set()
    for entry_data in entry_data_list:
        for tag in entry_data.get("suggested_tags", []):
            code = tag.get("category_code")
            if code:
                category_codes.add(code)

    if not category_codes:
        return []

    ledger_id = entries[0].ledger_id if entries else None
    if not ledger_id:
        return []

    categories = _ensure_tag_categories(db, ledger_id, category_codes)

    tag_mappings: list[dict[str, Any]] = []
    for entry, entry_data in zip(entries, entry_data_list):
        for tag in entry_data.get("suggested_tags", []):
            category_code = tag.get("category_code")
            tag_value = tag.get("tag_value", "")
            if not category_code or not tag_value:
                continue

            category = categories.get(category_code)
            if not category:
                continue

            normalized_value = tag_value.strip().lower()
            tag_mappings.append({
                "entry_id": entry.id,
                "ledger_id": entry.ledger_id,
                "category_id": category.id,
                "tag_name": f"{category_code}:{tag_value}",
                "tag_type": category_code,
                "tag_value": tag_value,
                "tag_value_normalized": normalized_value,
                "display_name": tag.get("display_name") or tag_value,
                "weight": tag.get("weight", 1.0),
                "tag_source": tag.get("tag_source", "rule"),
                "confidence": tag.get("confidence", 0.8),
                "reviewed_by_user": False,
                "vector_pending": True,
            })

    return tag_mappings


def _entry_rows_to_duplicate_keys(
    rows: list[Any],
) -> set[tuple[str, ...]]:
    """将分录查询结果转换为去重口径集合。"""
    return {
        _entry_duplicate_key(
            {
                "voucher_no": row.voucher_no,
                "voucher_date": row.voucher_date,
                "summary": row.summary,
                "account_code": row.account_code,
                "account_name": row.account_name,
                "debit_amount": row.debit_amount,
                "credit_amount": row.credit_amount,
                "counterparty": row.counterparty,
            }
        )
        for row in rows
    }


def _accounting_entry_identity_columns():
    return (
        AccountingEntry.voucher_no,
        AccountingEntry.voucher_date,
        AccountingEntry.summary,
        AccountingEntry.account_code,
        AccountingEntry.account_name,
        AccountingEntry.debit_amount,
        AccountingEntry.credit_amount,
        AccountingEntry.counterparty,
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


def _existing_ledger_voucher_no_to_id(db: Session, ledger_id: int) -> dict[str, int]:
    """读取账簿已有凭证号到凭证 ID 的映射，避免违反 ledger_id + voucher_no 唯一约束。"""
    rows = (
        db.query(Voucher.voucher_no, Voucher.id)
        .filter(Voucher.ledger_id == ledger_id)
        .all()
    )
    return {row.voucher_no: row.id for row in rows if row.voucher_no}


def process_day_book_import(db: Session, job: ImportJob) -> DayBookProcessingResult:
    """
    处理序时簿导入任务

    功能描述：按 voucher_no 分组合并分录为凭证，校验借贷平衡，检测跳号，
              生成检测报告，并保存分录到数据库。
    业务逻辑：
        1. 获取任务关联的源文件
        2. 解析文件得到分录列表
        3. 按 voucher_no 分组，为每组分配连续行号
        4. 逐凭证校验借贷平衡
        5. 检测凭证号连续性（跳号）
        6. 生成 DayBookReport 并保存分录到数据库
        7. 解析科目层级，生成 EntryTag，关联 Counterparty
        8. 执行逻辑校验、风险案例匹配、向量索引

    会计口径：
        - 同凭证号分录按导入顺序分配 entry_line_no
        - 借贷平衡校验使用 Decimal 精确计算
        - 跳号检测基于凭证号数字部分排序
        - 一级科目保留；强制二级科目保留完整层级；其余下级段转 EntryTag

    Args:
        db: 数据库会话
        job: 导入任务对象

    Returns:
        DayBookProcessingResult: 处理结果，包含检测报告和创建的分录数

    注意事项：
        1. 仅处理 .xlsx, .xls, .csv 格式的会计凭证文件
        2. 缺少 voucher_no 的分录会被单独分组（以 __no_voucher__:index 标识）
        3. 跳号检测仅适用于包含数字的凭证号
    """
    try:
        # 防止同一个导入任务被 Step3 重复触发时重复落库。
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
        existing_keys = _existing_entry_duplicate_keys(db, job.id)
        if job.ledger_id is not None:
            existing_keys |= _existing_ledger_entry_duplicate_keys(db, job.ledger_id)

        # 获取任务关联的源文件
        files = db.query(SourceFile).filter(SourceFile.import_job_id == job.id).all()

        all_entries: list[dict[str, Any]] = []
        total_created = 0
        last_parse_diagnostics: dict[str, Any] | None = None
        total_parsed_entries = 0

        for source_file in files:
            file_type = source_file.file_type.lower()
            if file_type not in {"xlsx", "xls", "csv", "tsv"}:
                continue

            # 统一结构化解析引擎（自适应模板 + evolution 规则 + 规则引擎回退）
            parse_result = parse_structured_accounting_entries(resolve_storage_path(source_file.storage_path), db=db)
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
                return DayBookProcessingResult(
                    success=False,
                    error_message="解析到的分录均已存在于当前账套/任务中，未新增分录。如需全量重导请更换账套或清理已有分录。",
                    parse_diagnostics=last_parse_diagnostics,
                )
            if job.ledger_id is not None:
                ledger_entry_count = (
                    db.query(AccountingEntry)
                    .filter(AccountingEntry.ledger_id == job.ledger_id)
                    .count()
                )
                if ledger_entry_count > 0:
                    return DayBookProcessingResult(
                        success=True,
                        entries_created=0,
                        report=None,
                    )
            return DayBookProcessingResult(
                success=False,
                error_message="未解析到有效分录数据，请检查表头列名是否包含凭证号、日期、摘要、科目、借贷金额",
                parse_diagnostics=last_parse_diagnostics,
            )

        # 按 parse_group_key 分组并分配分录行号（续行文件按顺序推理行号）
        _assign_entry_line_numbers(all_entries)

        # 准备逻辑校验数据
        entries_for_check: list[dict[str, Any]] = []
        voucher_types: list[str | None] = []

        for entry_data in all_entries:
            # 提取凭证字用于逻辑校验
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

        # 执行逻辑校验
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

        # 生成校验报告
        logic_report = generate_batch_report(logic_check_results)

        day_book_report = _build_day_book_report(all_entries)
        unbalanced_vouchers = day_book_report.unbalanced_vouchers
        missing_voucher_nos = day_book_report.missing_voucher_nos
        total_vouchers = day_book_report.total_vouchers
        skip_count = day_book_report.skip_count
        unbalanced_count = day_book_report.unbalanced_count
        completeness_score = day_book_report.completeness_score

        import uuid
        trace_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())

        db.add(
            ExecutionAuditLog(
                trace_id=trace_id,
                request_id=request_id,
                service_name="audit_day_book_service",
                tool_name="process_day_book_import",
                execution_source="api",
                business_object_type="import_job",
                business_object_id=str(job.id),
                ledger_id=job.ledger_id,
                project_id=job.project_id,
                status="started",
                risk_level="low",
                input_summary={
                    "total_vouchers": total_vouchers,
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
                tool_name="process_day_book_import",
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

        # 使用 ORM 对象批量保存 AccountingEntry，便于获取 entry_id 并关联 Tag
        entry_objects: list[AccountingEntry] = []
        for entry_data in all_entries:
            source_file_id = entry_data.get("source_file_id")
            voucher_no = entry_data.get("voucher_no") or ""
            voucher_id = voucher_no_to_id.get(voucher_no)

            # 解析并关联往来单位
            counterparty_name = entry_data.get("resolved_counterparty") or entry_data.get("counterparty")
            counterparty_id = _resolve_counterparty(db, counterparty_name)

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
                # 原始导入值，保留审计追溯
                account_code=entry_data.get("account_code"),
                account_name=entry_data.get("account_name"),
                # 解析后的归一化科目，用于后续财务计算
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

        # 批量创建 EntryTag
        tag_mappings = _build_entry_tags_for_import(db, entry_objects, all_entries)
        if tag_mappings:
            db.bulk_insert_mappings(EntryTag, tag_mappings)

        db.add(
            ExecutionAuditLog(
                trace_id=trace_id,
                request_id=request_id,
                service_name="audit_day_book_service",
                tool_name="process_day_book_import",
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

        # 向量同步在事务外执行，避免阻塞导入主流程
        try:
            vector_service = EntryTagVectorService(db)
            sync_result = vector_service.sync_pending(limit=200)
            # 记录同步结果，但不影响导入成功状态
            db.add(
                ExecutionAuditLog(
                    trace_id=trace_id,
                    request_id=request_id,
                    service_name="audit_day_book_service",
                    tool_name="process_day_book_import",
                    execution_source="api",
                    business_object_type="import_job",
                    business_object_id=str(job.id),
                    ledger_id=job.ledger_id,
                    project_id=job.project_id,
                    status="vector_sync_attempted",
                    risk_level="low",
                    input_summary=sync_result,
                )
            )
            db.commit()
        except Exception as vector_exc:
            db.add(
                ExecutionAuditLog(
                    trace_id=trace_id,
                    request_id=request_id,
                    service_name="audit_day_book_service",
                    tool_name="process_day_book_import",
                    execution_source="api",
                    business_object_type="import_job",
                    business_object_id=str(job.id),
                    ledger_id=job.ledger_id,
                    project_id=job.project_id,
                    status="vector_sync_failed",
                    risk_level="low",
                    error_message=str(vector_exc),
                )
            )
            db.commit()

        db.add(
            ExecutionAuditLog(
                trace_id=trace_id,
                request_id=request_id,
                service_name="audit_day_book_service",
                tool_name="process_day_book_import",
                execution_source="api",
                business_object_type="import_job",
                business_object_id=str(job.id),
                ledger_id=job.ledger_id,
                project_id=job.project_id,
                status="completed",
                risk_level="low",
                input_summary={
                    "entry_count": total_created,
                    "tag_count": len(tag_mappings),
                    "skip_count": skip_count,
                    "unbalanced_count": unbalanced_count,
                    "completeness_score": completeness_score,
                },
            )
        )
        db.commit()

        return DayBookProcessingResult(
            success=True,
            entries_created=total_created,
            report=day_book_report,
        )

    except Exception as exc:
        db.rollback()
        import uuid
        trace_id = str(uuid.uuid4())
        request_id = str(uuid.uuid4())
        db.add(
            ExecutionAuditLog(
                trace_id=trace_id,
                request_id=request_id,
                service_name="audit_day_book_service",
                tool_name="process_day_book_import",
                execution_source="api",
                business_object_type="import_job",
                business_object_id=str(job.id),
                ledger_id=job.ledger_id,
                project_id=job.project_id,
                status="failed",
                risk_level="high",
                error_message=str(exc),
            )
        )
        db.commit()
        return DayBookProcessingResult(
            success=False,
            error_message=str(exc),
        )


def _existing_staging_duplicate_keys(db: Session, job_id: int) -> set[tuple[str, ...]]:
    rows = (
        db.query(StagingAccountingEntry)
        .filter(StagingAccountingEntry.import_job_id == job_id)
        .all()
    )
    keys: set[tuple[str, ...]] = set()
    for row in rows:
        keys.add(
            _entry_duplicate_key(
                {
                    "voucher_no": row.voucher_no,
                    "voucher_date": row.voucher_date,
                    "summary": row.summary,
                    "account_code": row.account_code,
                    "account_name": row.account_name,
                    "debit_amount": row.debit_amount,
                    "credit_amount": row.credit_amount,
                    "counterparty": row.counterparty,
                }
            )
        )
    return keys


def _staging_row_from_entry_data(
    job: ImportJob,
    entry_data: dict[str, Any],
    *,
    parse_diagnostics: dict[str, Any] | None,
) -> StagingAccountingEntry:
    from app.services.audit.voucher_signature_service import extract_source_preparer_name

    import_mode = get_import_mode(job.source_type)
    original_row = dict(entry_data.get("original_row") or {})
    if entry_data.get("requires_llm_resolution"):
        original_row["_requires_llm_resolution"] = True
    preparer_name = extract_source_preparer_name(entry_data)
    return StagingAccountingEntry(
        import_job_id=job.id,
        organization_id=job.organization_id,
        ledger_id=job.ledger_id,
        project_id=job.project_id,
        entity_org_id=job.organization_id,
        import_mode=import_mode,
        source_type=job.source_type,
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
        entry_line_no=entry_data.get("entry_line_no", 1),
        source_file_id=entry_data.get("source_file_id"),
        original_row=original_row,
        normalized_text=entry_data.get("normalized_text", ""),
        entry_tags_payload=entry_data.get("suggested_tags"),
        parse_diagnostics=parse_diagnostics,
        source_preparer_name=preparer_name,
        review_status="draft",
    )


def _parse_day_book_entries_from_job(
    db: Session,
    job: ImportJob,
) -> tuple[list[dict[str, Any]], DayBookReport | None, dict[str, Any] | None, str | None]:
    """解析源文件为分录列表，并生成序时簿检测报告（不落库）。"""
    files = db.query(SourceFile).filter(SourceFile.import_job_id == job.id).all()
    all_entries: list[dict[str, Any]] = []
    last_parse_diagnostics: dict[str, Any] | None = None
    total_parsed_entries = 0
    existing_keys = _existing_staging_duplicate_keys(db, job.id)

    from app.services.doc_parsing.structured_parse_options import (
        parse_options_from_job_draft,
        reset_parse_options,
        set_parse_options,
    )
    from app.services.doc_parsing.parse_context import reset_parse_context, set_parse_context

    parse_options = parse_options_from_job_draft(job.draft_data)
    options_token = set_parse_options(parse_options)
    context_tokens = set_parse_context(db=db, ledger_id=job.ledger_id)
    try:
        for source_file in files:
            file_type = source_file.file_type.lower()
            if file_type not in {"xlsx", "xls", "csv", "tsv"}:
                continue
            parse_result = parse_structured_accounting_entries(
                resolve_storage_path(source_file.storage_path),
                db=db,
                parse_options=parse_options,
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
    finally:
        reset_parse_options(options_token)
        reset_parse_context(*context_tokens)

    if not all_entries:
        if total_parsed_entries > 0:
            return [], None, last_parse_diagnostics, None
        return (
            [],
            None,
            last_parse_diagnostics,
            "未解析到有效分录数据，请检查表头列名是否包含凭证号、日期、摘要、科目、借贷金额",
        )

    _assign_entry_line_numbers(all_entries)
    day_book_report = _build_day_book_report(all_entries)
    return all_entries, day_book_report, last_parse_diagnostics, None


def _day_book_report_from_entry_dicts(all_entries: list[dict[str, Any]]) -> DayBookReport:
    return _build_day_book_report(all_entries)


def preview_day_book_import(db: Session, job: ImportJob) -> DayBookProcessingResult:
    """规则解析并写入 staging 草稿，不入正式账套。"""
    try:
        if job.ledger_id:
            from app.services.doc_parsing.dimension_readiness_service import assess_ledger_dimension_readiness

            readiness = assess_ledger_dimension_readiness(db, job.ledger_id)
            if not readiness.get("ready_for_structured_import"):
                blockers = readiness.get("blockers") or []
                message = blockers[0].get("message") if blockers else "请先审阅本账簿 tag 规则与维度分类"
                return DayBookProcessingResult(success=False, entries_created=0, error_message=message)

        existing_staging_count = (
            db.query(StagingAccountingEntry)
            .filter(StagingAccountingEntry.import_job_id == job.id)
            .count()
        )
        if existing_staging_count > 0:
            staging_rows = (
                db.query(StagingAccountingEntry)
                .filter(StagingAccountingEntry.import_job_id == job.id)
                .order_by(
                    StagingAccountingEntry.voucher_no,
                    StagingAccountingEntry.entry_line_no,
                )
                .all()
            )
            entry_dicts = [
                {
                    "voucher_no": row.voucher_no,
                    "voucher_date": row.voucher_date,
                    "debit_amount": row.debit_amount,
                    "credit_amount": row.credit_amount,
                    "entry_line_no": row.entry_line_no,
                }
                for row in staging_rows
            ]
            return DayBookProcessingResult(
                success=True,
                entries_created=existing_staging_count,
                report=_day_book_report_from_entry_dicts(entry_dicts),
            )

        all_entries, day_book_report, parse_diagnostics, parse_error = _parse_day_book_entries_from_job(db, job)
        if parse_error:
            return DayBookProcessingResult(
                success=False,
                error_message=parse_error,
                parse_diagnostics=parse_diagnostics,
            )

        for entry_data in all_entries:
            db.add(
                _staging_row_from_entry_data(
                    job,
                    entry_data,
                    parse_diagnostics=parse_diagnostics,
                )
            )
        db.commit()

        try:
            from app.services.audit.vectorize_staging_service import vectorize_staging_job

            vectorize_staging_job(db, job.id)
        except Exception:
            pass

        return DayBookProcessingResult(
            success=True,
            entries_created=len(all_entries),
            report=day_book_report,
        )
    except Exception as exc:
        db.rollback()
        return DayBookProcessingResult(success=False, error_message=str(exc))


def confirm_day_book_import(
    db: Session,
    job: ImportJob,
    *,
    approved_by_user_id: int | None = None,
) -> DayBookProcessingResult:
    """将 staging 草稿确认入账，生成未审核凭证分录。"""
    try:
        staging_rows = (
            db.query(StagingAccountingEntry)
            .filter(StagingAccountingEntry.import_job_id == job.id)
            .order_by(
                StagingAccountingEntry.voucher_no,
                StagingAccountingEntry.entry_line_no,
            )
            .all()
        )
        if not staging_rows:
            return DayBookProcessingResult(
                success=False,
                error_message="没有可确认的草稿分录，请先上传并解析文件",
            )

        from app.services.audit.staging_review_service import (
            VERIFIED_REVIEW_STATUSES,
            group_staging_rows,
            validate_staging_ready_for_confirm,
        )
        from app.services.audit.voucher_signature_service import (
            signature_from_staging_group,
            stamp_voucher_signatures,
        )
        from datetime import datetime, timezone

        validation_error = validate_staging_ready_for_confirm(staging_rows)
        if validation_error:
            return DayBookProcessingResult(success=False, error_message=validation_error)

        staging_groups = group_staging_rows(staging_rows)
        voucher_signatures = {
            key: signature_from_staging_group(group) for key, group in staging_groups.items()
        }
        approved_at = datetime.now(timezone.utc) if approved_by_user_id else None

        ledger_id = job.ledger_id
        if ledger_id is None:
            import_mode = get_import_mode(job.source_type)
            if import_mode == "B1":
                if not job.project_id:
                    return DayBookProcessingResult(
                        success=False,
                        error_message="审计凭证导入需要指定 project_id",
                    )
                from app.services.audit.working_ledger_service import get_or_create_working_ledger

                working_ledger = get_or_create_working_ledger(
                    db,
                    project_id=job.project_id,
                    entity_org_id=job.organization_id,
                )
                ledger_id = working_ledger.id
                job.ledger_id = ledger_id
                db.flush()
            else:
                return DayBookProcessingResult(
                    success=False,
                    error_message="确认入账需要指定账套（ledger_id）",
                )

        all_entries: list[dict[str, Any]] = []
        from app.services.audit.dimension_sync_service import enrich_tags_from_master

        for row in staging_rows:
            base_code = row.resolved_account_code or row.account_code or ""
            enriched_tags = enrich_tags_from_master(
                db,
                ledger_id,
                row.entry_tags_payload,
                account_code=base_code,
            )
            all_entries.append(
                {
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
                    "entry_line_no": row.entry_line_no,
                    "source_file_id": row.source_file_id,
                    "original_row": row.original_row or {},
                    "normalized_text": row.normalized_text or "",
                    "suggested_tags": enriched_tags,
                    "requires_llm_resolution": bool((row.original_row or {}).get("_requires_llm_resolution")),
                    "review_status": row.review_status,
                }
            )

        voucher_groups: dict[str, list[dict[str, Any]]] = {}
        for idx, entry_data in enumerate(all_entries):
            voucher_no = entry_data.get("voucher_no") or f"__no_voucher__:{idx}"
            voucher_groups.setdefault(voucher_no, []).append(entry_data)

        unbalanced_vouchers: list[UnbalancedVoucher] = []
        for voucher_no, entries in voucher_groups.items():
            if voucher_no.startswith("__no_voucher__"):
                continue
            is_balanced, debit_total, credit_total, difference = _validate_voucher_balance(entries)
            if not is_balanced:
                unbalanced_vouchers.append(
                    UnbalancedVoucher(
                        voucher_no=voucher_no,
                        debit_total=debit_total,
                        credit_total=credit_total,
                        difference=difference,
                        entry_count=len(entries),
                    )
                )

        existing_ledger_keys: set[tuple[str, ...]] = set()
        if ledger_id is not None:
            existing_ledger_keys = _existing_ledger_entry_duplicate_keys(db, ledger_id)

        entries_to_create: list[dict[str, Any]] = []
        for entry_data in all_entries:
            dup_key = _entry_duplicate_key(entry_data)
            if dup_key in existing_ledger_keys:
                continue
            existing_ledger_keys.add(dup_key)
            entries_to_create.append(entry_data)

        if not entries_to_create:
            db.query(StagingAccountingEntry).filter(
                StagingAccountingEntry.import_job_id == job.id
            ).delete(synchronize_session=False)
            db.commit()
            return DayBookProcessingResult(
                success=True,
                entries_created=0,
                report=None,
            )

        voucher_groups = {}
        for idx, entry_data in enumerate(entries_to_create):
            voucher_no = entry_data.get("voucher_no") or f"__no_voucher__:{idx}"
            voucher_groups.setdefault(voucher_no, []).append(entry_data)

        existing_voucher_no_to_id = _existing_ledger_voucher_no_to_id(db, ledger_id)
        voucher_no_to_id: dict[str, int] = dict(existing_voucher_no_to_id)

        for voucher_no, entries in voucher_groups.items():
            if voucher_no.startswith("__no_voucher__") or voucher_no in existing_voucher_no_to_id:
                continue
            first_entry = entries[0]
            voucher_debit_total = sum(
                Decimal(str(e.get("debit_amount", "0"))) for e in entries if e.get("debit_amount")
            ) or Decimal("0")
            voucher_credit_total = sum(
                Decimal(str(e.get("credit_amount", "0"))) for e in entries if e.get("credit_amount")
            ) or Decimal("0")
            voucher = Voucher(
                organization_id=job.organization_id,
                ledger_id=ledger_id,
                voucher_no=voucher_no,
                voucher_date=first_entry.get("voucher_date"),
                summary=(first_entry.get("summary") or "")[:200],
                total_debit=voucher_debit_total,
                total_credit=voucher_credit_total,
                import_job_id=job.id,
                status="pending",
                source_type="import",
                period_id=resolve_voucher_period_id(job, first_entry.get("voucher_date")),
            )
            sig_key = f"{voucher_no}|{(first_entry.get('voucher_date').isoformat() if first_entry.get('voucher_date') else '')}"
            sig = voucher_signatures.get(sig_key) or {}
            stamp_voucher_signatures(
                voucher,
                source_preparer_name=sig.get("source_preparer_name"),
                cross_reviewed_by_user_id=sig.get("cross_reviewed_by_user_id"),
                cross_reviewed_at=sig.get("cross_reviewed_at"),
                approved_by_user_id=approved_by_user_id,
                approved_at=approved_at,
            )
            db.add(voucher)

        db.flush()

        for voucher in db.query(Voucher).filter(Voucher.import_job_id == job.id).all():
            voucher_no_to_id[voucher.voucher_no] = voucher.id

        entry_objects: list[AccountingEntry] = []
        for entry_data in entries_to_create:
            voucher_no = entry_data.get("voucher_no") or ""
            counterparty_name = entry_data.get("counterparty")
            counterparty_id = _resolve_counterparty(db, counterparty_name)
            entry = AccountingEntry(
                organization_id=job.organization_id,
                ledger_id=ledger_id,
                voucher_id=voucher_no_to_id.get(voucher_no),
                import_job_id=job.id,
                source_file_id=entry_data.get("source_file_id"),
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
                review_status=(
                    entry_data.get("review_status")
                    if entry_data.get("review_status") in VERIFIED_REVIEW_STATUSES
                    else "verified"
                ),
                post_status="draft",
                requires_llm_resolution=bool(entry_data.get("requires_llm_resolution")),
            )
            entry_objects.append(entry)
            db.add(entry)

        db.flush()
        tag_mappings = _build_entry_tags_for_import(db, entry_objects, entries_to_create)
        if tag_mappings:
            db.bulk_insert_mappings(EntryTag, tag_mappings)

        from app.services.audit.structured_import_service import create_bank_name_control_findings

        create_bank_name_control_findings(db, job, staging_rows)

        db.query(StagingAccountingEntry).filter(
            StagingAccountingEntry.import_job_id == job.id
        ).delete(synchronize_session=False)

        db.commit()

        try:
            vector_service = EntryTagVectorService(db)
            vector_service.sync_pending(limit=200)
        except Exception:
            pass

        return DayBookProcessingResult(
            success=True,
            entries_created=len(entry_objects),
            report=None,
        )
    except Exception as exc:
        db.rollback()
        return DayBookProcessingResult(success=False, error_message=str(exc))


def cancel_day_book_import(db: Session, job: ImportJob) -> None:
    db.query(StagingAccountingEntry).filter(
        StagingAccountingEntry.import_job_id == job.id
    ).delete(synchronize_session=False)
    job.status = "cancelled"
    db.commit()

