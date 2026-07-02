"""
导入服务

支持分离的凭证处理和原始文件处理流程
集成：
- 自适应格式模板
- 多维度 tags 语义标签
- 逻辑校验（摘要-科目匹配校验）
- 风险案例匹配
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
import json
from pathlib import Path
import threading
from typing import Any
from uuid import uuid4

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    AccountingEntry,
    DocumentChunk,
    EntryTag,
    ImportJob,
    Organization,
    SourceFile,
)
from app.services.audit_day_book_service import (
    DayBookProcessingResult,
    DayBookReport,
    build_accounting_entry_duplicate_key,
    process_day_book_import,
)
from app.services.draft_archive_service import auto_archive_draft
from app.services.register_ingestion_service import classify_and_ingest_register
from app.services.import_routing_service import (
    AI_EVIDENCE_SOURCE_TYPES,
    get_import_output_path,
    is_day_book_source_type,
    should_persist_structured_entries,
)
from app.services.period_detection_service import suggest_period_for_job
from app.services.data_validator import EntryQuality, ImportQualityReport, generate_quality_report
from app.services.entry_tags_service import build_semantic_text, generate_entry_tags
from app.services.file_parser_service import ParseResult, build_parse_diagnostics, extract_text, parse_entries
from app.services.source_document_service import SourceDocumentResult, classify_document
from app.services.logic_check_service import (
    BatchCheckReport,
    check_entry_logic,
    generate_batch_report,
)
from app.services.risk_rule_service import generate_risks
from app.services.risk_case_library import enhance_entry_with_risk_analysis
from app.services.ledger_context_service import resolve_or_create_organization_for_ledger
from app.services.tagging_service import suggest_tags, suggest_voucher_type
from app.services.vector_store_service import chunk_hash, chunk_text, safe_vector_store
from app.services.voucher_service import (
    VoucherEntryLine,
    VoucherSourceType,
    VoucherStatus,
    create_voucher,
    get_voucher_lines,
)
from app.storage.local_storage import resolve_storage_path, save_upload


# 会计凭证文件类型
ACCOUNTING_FILE_TYPES = {".xlsx", ".xls", ".csv"}

# 原始文件类型
SOURCE_FILE_TYPES = {".pdf", ".txt", ".md", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".xml", ".ofd"}

DOCUMENT_TYPE_LABELS = {
    "invoice": "发票",
    "bank_statement": "银行流水",
    "contract": "合同",
    "inventory_receipt": "入库单",
    "salary_table": "工资表",
    "expense_document": "费用单据",
    "receipt": "收据",
    "general": "通用资料",
}


@dataclass
class ProcessingResult:
    """处理结果"""
    file_type: str  # "accounting_entry" | "source_file" | "register_ledger"
    filename: str
    success: bool
    entries_created: int = 0
    text_extracted: str = ""
    template_name: str | None = None
    quality_score: float = 0.0
    error_message: str | None = None
    register_type: str | None = None
    register_count: int = 0
    register_ids: list[int] = field(default_factory=list)
    module_label: str | None = None
    module_path: str | None = None
    module_registrations: list[dict[str, Any]] = field(default_factory=list)
    semantic_decomposition: dict[str, Any] = field(default_factory=dict)
    semantic_tags: list[str] = field(default_factory=list)
    risk_hints: list[dict[str, Any]] = field(default_factory=list)
    draft_only: bool = False
    archive_path: str | None = None
    archive_context: dict[str, Any] = field(default_factory=dict)
    parse_diagnostics: dict[str, Any] | None = None
    recommended_mode: str | None = None


@dataclass
class ImportReport:
    """导入报告"""
    job_id: int
    total_files: int
    success_files: int
    failed_files: int
    total_entries: int
    output_path: str = "ai_draft"
    period_suggestion: dict[str, Any] | None = None
    day_book_report: DayBookReport | None = None
    register_summary: list[dict[str, Any]] | None = None
    quality_report: ImportQualityReport | None = None
    file_results: list[ProcessingResult] = field(default_factory=list)
    logic_report: BatchCheckReport | None = None  # 合并的逻辑校验报告
    error_message: str | None = None
    parse_diagnostics: dict[str, Any] | None = None


def create_import_job(
    db: Session,
    organization_name: str,
    industry: str | None,
    fiscal_year: int | None,
    source_type: str = "voucher_import",
    ledger_id: int | None = None,
    audit_scope_type: str | None = None,
    audit_period_id: int | None = None,
    audit_account_codes: list[str] | None = None,
    project_id: int | None = None,
) -> ImportJob:
    """
    创建导入任务

    功能描述：创建新的导入任务，支持指定数据来源类型
    业务逻辑：
        1. 创建 Organization 记录
        2. 创建 ImportJob 记录，并设置 source_type

    Args:
        db: 数据库会话
        organization_name: 企业名称
        industry: 行业
        fiscal_year: 会计年度
        source_type: 数据来源类型
        ledger_id: 账簿 ID
        audit_scope_type: 审计范围类型
        audit_period_id: 审计期间 ID
        audit_account_codes: 审计科目代码列表
        project_id: 项目 ID

    Returns:
        ImportJob: 创建的导入任务
    """
    organization = db.query(Organization).filter(Organization.name == organization_name).first()
    if organization is None:
        organization = Organization(name=organization_name, industry=industry, fiscal_year=fiscal_year)
        db.add(organization)
        db.flush()
    if ledger_id is not None:
        organization_id = resolve_or_create_organization_for_ledger(
            db,
            ledger_id,
            organization_name=organization_name,
            industry=industry,
            fiscal_year=fiscal_year,
        )
        organization = db.get(Organization, organization_id)
    if organization is None:
        organization = Organization(name=organization_name, industry=industry, fiscal_year=fiscal_year)
        db.add(organization)
        db.flush()
    job = ImportJob(
        organization_id=organization.id,
        ledger_id=ledger_id,
        source_type=source_type,
        audit_scope_type=audit_scope_type,
        audit_period_id=audit_period_id,
        audit_account_codes=audit_account_codes,
        project_id=project_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def attach_file(db: Session, job: ImportJob, file: UploadFile) -> SourceFile:
    """附加文件到任务"""
    storage_path = save_upload(file)
    file_type = Path(file.filename or storage_path).suffix.lower().lstrip(".") or "unknown"

    # 【修复】自动关联账簿ID：如果 job 没有 ledger_id，尝试从同 organization 的其他 job 获取
    ledger_id = job.ledger_id
    if ledger_id is None:
        # 查找同 organization 下最近有 ledger_id 的其他 job
        other_job = (
            db.query(ImportJob)
            .filter(
                ImportJob.organization_id == job.organization_id,
                ImportJob.ledger_id.isnot(None),
                ImportJob.id != job.id,
            )
            .order_by(ImportJob.id.desc())
            .first()
        )
        if other_job:
            ledger_id = other_job.ledger_id

    source_file = SourceFile(
        organization_id=job.organization_id,
        import_job_id=job.id,
        ledger_id=ledger_id,
        filename=file.filename or Path(storage_path).name,
        file_type=file_type,
        storage_path=storage_path,
    )
    job.file_count += 1
    db.add(source_file)
    db.commit()
    db.refresh(source_file)
    return source_file


def _normalize_file_type(file_type: str) -> str:
    return file_type.lower() if file_type.startswith(".") else f".{file_type.lower()}"


def _is_accounting_file(file_type: str) -> bool:
    """判断是否为会计凭证文件"""
    return _normalize_file_type(file_type) in ACCOUNTING_FILE_TYPES


def _is_source_file(file_type: str) -> bool:
    """判断是否为原始文件"""
    return _normalize_file_type(file_type) in SOURCE_FILE_TYPES


def _normalize_document_type(document_type: str) -> str:
    if document_type == "inventory_receipt":
        return "inventory"
    return document_type


def _extract_source_summary(result: SourceDocumentResult) -> dict[str, Any]:
    data = result.data or {}
    document_type = _normalize_document_type(result.document_type)
    key_fields: dict[str, Any] = {}

    if result.document_type == "invoice":
        key_fields = {
            "date": data.get("invoice_date"),
            "amount": data.get("total_amount"),
            "counterparty": data.get("seller_name") or data.get("buyer_name"),
        }
    elif result.document_type == "bank_statement":
        transactions = data.get("transactions") or []
        first_transaction = transactions[0] if transactions else {}
        key_fields = {
            "date": first_transaction.get("transaction_date"),
            "amount": first_transaction.get("amount"),
            "counterparty": first_transaction.get("counterparty"),
        }
    elif result.document_type == "contract":
        key_fields = {
            "date": data.get("sign_date"),
            "amount": data.get("amount"),
            "counterparty": data.get("party_b") or data.get("party_a"),
        }
    elif result.document_type == "inventory_receipt":
        key_fields = {
            "date": data.get("receipt_date"),
            "amount": data.get("total_amount"),
            "counterparty": data.get("supplier"),
        }
    elif result.document_type == "salary_table":
        key_fields = {
            "date": data.get("salary_period"),
            "amount": data.get("total_amount") or data.get("gross_amount"),
            "counterparty": None,
        }
    elif result.document_type == "expense_document":
        key_fields = {
            "date": data.get("expense_date") or data.get("reimbursement_date"),
            "amount": data.get("total_amount") or data.get("expense_amount"),
            "counterparty": data.get("reimbursement_person") or data.get("applicant"),
        }
    elif result.document_type == "receipt":
        key_fields = {
            "date": data.get("receipt_date"),
            "amount": data.get("amount"),
            "counterparty": data.get("payer") or data.get("payee"),
        }

    summary_parts = []
    label = DOCUMENT_TYPE_LABELS.get(result.document_type, "通用资料")
    if result.confidence > 0:
        summary_parts.append(f"识别为{label}，置信度{round(result.confidence * 100)}%")
    else:
        summary_parts.append("系统未能确认资料类型")
    if key_fields.get("date"):
        summary_parts.append(f"日期{key_fields['date']}")
    if key_fields.get("amount") is not None:
        summary_parts.append(f"金额{key_fields['amount']}")
    if key_fields.get("counterparty"):
        summary_parts.append(f"对方单位{key_fields['counterparty']}")

    return {
        "document_type": document_type,
        "document_type_label": label,
        "confidence": result.confidence,
        "summary": "；".join(summary_parts),
        "voucher_date": key_fields.get("date"),
        "amount": key_fields.get("amount"),
        "counterparty": key_fields.get("counterparty"),
    }


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _save_parse_feedback(source_file: SourceFile, feedback: dict[str, Any], raw_text: str | None) -> None:
    source_file.extracted_text = json.dumps(
        {
            "parse_feedback": feedback,
            "raw_text_preview": (raw_text or "")[:1000],
        },
        ensure_ascii=False,
        default=_json_default,
    )


def _index_text(db: Session, organization_id: int, source_type: str, source_id: int, text: str, payload: dict) -> None:
    """索引文本到向量存储"""
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


def _voucher_date_from_entry(entry_data: dict[str, Any]) -> date:
    """从 entry_data 中解析凭证日期，失败则返回今天。"""
    raw = entry_data.get("voucher_date")
    if isinstance(raw, date):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return date.fromisoformat(raw)
        except ValueError:
            pass
    return date.today()


def _build_voucher_group_lines(
    voucher_no: str,
    group_items: list[tuple[int, dict[str, Any]]],
    logic_check_results: list[Any],
    existing_keys: set[str],
    source_file_id: int,
) -> tuple[list[VoucherEntryLine], list[str], list[str], bool, str | None]:
    """
    构建单个凭证组的 VoucherEntryLine 列表。

    返回值：
        - lines: VoucherEntryLine 列表
        - semantic_texts: 与 lines 一一对应的语义文本
        - all_tag_names: 本组涉及的所有 tag 名称
        - all_duplicate: 是否全部行都是重复
        - error_message: 错误信息（如部分重复导致无法保证平衡）
    """
    lines: list[VoucherEntryLine] = []
    semantic_texts: list[str] = []
    all_tag_names: list[str] = []
    all_duplicate = True

    for raw_index, entry_data in group_items:
        duplicate_key = build_accounting_entry_duplicate_key(entry_data)
        is_duplicate = duplicate_key in existing_keys
        if not is_duplicate:
            all_duplicate = False
        else:
            continue

        tags = generate_entry_tags(entry_data)
        entry_data["tags"] = tags
        entry_data = enhance_entry_with_risk_analysis(entry_data)
        semantic_text = build_semantic_text(entry_data, tags)

        check_result = logic_check_results[raw_index]
        tag_dicts: list[dict[str, Any]] = [
            {"tag_type": "source", "tag_value": "source:import", "tag_source": "rule", "confidence": 1.0}
        ]
        for tag_name in tags:
            tag_dicts.append({"tag_type": "semantic", "tag_value": tag_name, "tag_source": "rule", "confidence": 1.0})
        if not check_result.is_consistent:
            for issue in check_result.issues:
                tag_dicts.append({
                    "tag_type": "logic_check",
                    "tag_value": f"逻辑校验:{issue.severity}:{issue.issue_type}",
                    "tag_source": "rule",
                    "confidence": 0.9,
                })
        for case in check_result.matched_risk_cases:
            tag_dicts.append({
                "tag_type": "risk_case",
                "tag_value": f"风险案例:{case['risk_type']}:{case['id']}",
                "tag_source": "rule",
                "confidence": 0.9,
            })

        all_tag_names.extend(tags)
        semantic_texts.append(semantic_text)

        line = VoucherEntryLine(
            account_code=entry_data.get("account_code"),
            account_name=entry_data.get("account_name"),
            summary=entry_data.get("summary"),
            debit_amount=Decimal(str(entry_data.get("debit_amount", 0))),
            credit_amount=Decimal(str(entry_data.get("credit_amount", 0))),
            counterparty=entry_data.get("counterparty"),
            source_file_id=source_file_id,
            original_row=entry_data.get("original_row"),
            normalized_text=entry_data.get("summary") or "",
            entity_id=entry_data.get("entity_id"),
            original_entity_name=entry_data.get("original_entity_name"),
            tags=tag_dicts,
        )
        lines.append(line)

    if not lines and all_duplicate:
        return lines, semantic_texts, list(set(all_tag_names)), True, None

    if not lines and not all_duplicate:
        return lines, semantic_texts, list(set(all_tag_names)), False, "凭证组未构建出有效分录行"

    return lines, semantic_texts, list(set(all_tag_names)), False, None


def _process_accounting_file(
    db: Session,
    job: ImportJob,
    source_file: SourceFile,
) -> tuple[ProcessingResult, list[str], BatchCheckReport | None, list[dict[str, Any]]]:
    """
    处理会计凭证文件

    流程：
    1. 解析文件（自适应模板匹配）
    2. 生成多维度 tags
    3. 逻辑校验（摘要-科目匹配）
    4. 风险案例匹配
    5. 按凭证号分组并强制借贷平衡校验
    6. 通过 voucher_service 创建凭证和分录
    7. 向量索引
    """
    try:
        parse_result = parse_entries(resolve_storage_path(source_file.storage_path))

        if not parse_result.entries:
            return (
                ProcessingResult(
                    file_type="accounting_entry",
                    filename=source_file.filename,
                    success=False,
                    error_message="未解析到有效分录数据",
                ),
                [],
                None,
                [],
            )

        entries_for_check: list[dict] = []
        voucher_types: list[str | None] = []
        for entry_data in parse_result.entries:
            class MockEntry:
                def __init__(self, d):
                    self.summary = d.get("summary", "")
                    self.account_name = d.get("account_name", "")
                    self.debit_amount = d.get("debit_amount", 0)
                    self.credit_amount = d.get("credit_amount", 0)
                    self.voucher_date = None
                    self.account_code = d.get("account_code", "")

            mock_entry = MockEntry(entry_data)
            voucher_type, _ = suggest_voucher_type(mock_entry)
            voucher_types.append(voucher_type)
            entries_for_check.append({
                "summary": entry_data.get("summary", ""),
                "debit_account": entry_data.get("debit_account_name", ""),
                "credit_account": entry_data.get("credit_account_name", ""),
                "debit_amount": entry_data.get("debit_amount", 0),
                "credit_amount": entry_data.get("credit_amount", 0),
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

        existing_keys = {
            build_accounting_entry_duplicate_key(
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
            for row in db.query(
                AccountingEntry.voucher_no,
                AccountingEntry.voucher_date,
                AccountingEntry.summary,
                AccountingEntry.account_code,
                AccountingEntry.account_name,
                AccountingEntry.debit_amount,
                AccountingEntry.credit_amount,
                AccountingEntry.counterparty,
            )
            .filter(AccountingEntry.import_job_id == job.id)
            .all()
        }

        # 按 voucher_no 分组
        groups: dict[str, list[tuple[int, dict[str, Any]]]] = {}
        for i, entry_data in enumerate(parse_result.entries):
            voucher_no = str(entry_data.get("voucher_no") or f"__no_voucher__:{i}").strip()
            groups.setdefault(voucher_no, []).append((i, entry_data))

        created_vouchers: list[Any] = []
        entries_created = 0
        all_tag_names: list[str] = []
        skipped_duplicate_vouchers = 0

        for voucher_no, group_items in groups.items():
            lines, semantic_texts, tag_names, all_duplicate, error_message = _build_voucher_group_lines(
                voucher_no,
                group_items,
                logic_check_results,
                existing_keys,
                source_file.id,
            )
            all_tag_names.extend(tag_names)

            if error_message:
                return (
                    ProcessingResult(
                        file_type="accounting_entry",
                        filename=source_file.filename,
                        success=False,
                        error_message=f"凭证 {voucher_no} 处理失败：{error_message}",
                    ),
                    [],
                    None,
                    [],
                )

            if all_duplicate:
                skipped_duplicate_vouchers += 1
                continue

            # 强制校验借贷平衡
            total_debit = sum(line.debit_amount for line in lines)
            total_credit = sum(line.credit_amount for line in lines)
            if total_debit != total_credit:
                return (
                    ProcessingResult(
                        file_type="accounting_entry",
                        filename=source_file.filename,
                        success=False,
                        error_message=f"凭证 {voucher_no} 借贷不平衡：借方合计 {total_debit}，贷方合计 {total_credit}",
                    ),
                    [],
                    None,
                    [],
                )

            voucher_date = _voucher_date_from_entry(group_items[0][1])
            summary = group_items[0][1].get("summary")
            ledger_id = source_file.ledger_id or job.ledger_id
            if not ledger_id:
                return (
                    ProcessingResult(
                        file_type="accounting_entry",
                        filename=source_file.filename,
                        success=False,
                        error_message="无法确定凭证所属账簿 ID",
                    ),
                    [],
                    None,
                    [],
                )

            voucher = create_voucher(
                db,
                ledger_id=ledger_id,
                organization_id=job.organization_id,
                voucher_no=voucher_no,
                voucher_date=voucher_date,
                summary=summary,
                lines=lines,
                source_type=VoucherSourceType.IMPORT,
                source_id=source_file.id,
                import_job_id=job.id,
                status=VoucherStatus.DRAFT,
                auto_commit=False,
            )
            created_vouchers.append(voucher)
            entries_created += len(lines)

            # 向量索引：根据创建后的分录 ID 与语义文本对应
            created_entries = get_voucher_lines(db, voucher.id)
            for entry, semantic_text in zip(created_entries, semantic_texts):
                check_result = logic_check_results[group_items[0][0]]
                _index_text(
                    db,
                    job.organization_id,
                    "accounting_entry",
                    entry.id,
                    semantic_text,
                    {
                        "organization_id": job.organization_id,
                        "import_job_id": job.id,
                        "voucher_no": entry.voucher_no,
                        "voucher_date": str(entry.voucher_date) if entry.voucher_date else None,
                        "account_name": entry.account_name,
                        "amount": float(entry.debit_amount or entry.credit_amount or 0),
                        "counterparty": entry.counterparty,
                        "tags": tag_names,
                        "is_consistent": check_result.is_consistent,
                        "risk_count": len(check_result.matched_risk_cases),
                    },
                )

        first_entry = parse_result.entries[0] if parse_result.entries else {}
        archive_feedback = {
            "document_type": "structured_ledger" if is_day_book_source_type(job.source_type) else "accounting_voucher",
            "document_type_label": "序时簿" if is_day_book_source_type(job.source_type) else "会计凭证",
            "voucher_date": first_entry.get("voucher_date"),
            "summary": f"解析 {entries_created} 条分录（跳过 {skipped_duplicate_vouchers} 张重复凭证）",
        }
        archive = _archive_source_file(db, job, source_file, archive_feedback)

        source_file.text_extract_status = "parsed_entries"
        source_file.extracted_text = (
            f"解析成功：{parse_result.template_name or '未知模板'}，"
            f"{entries_created}条分录，跳过{skipped_duplicate_vouchers}张重复凭证，"
            f"逻辑校验问题{logic_report.error_count}个"
        )

        return (
            ProcessingResult(
                file_type="accounting_entry",
                filename=source_file.filename,
                success=True,
                entries_created=entries_created,
                template_name=parse_result.template_name,
                quality_score=parse_result.quality_score,
                archive_path=archive.get("archive_path"),
                archive_context=archive,
            ),
            list(set(all_tag_names)),
            logic_report,
            parse_result.entries,
        )

    except Exception as exc:
        return (
            ProcessingResult(
                file_type="accounting_entry",
                filename=source_file.filename,
                success=False,
                error_message=str(exc),
            ),
            [],
            None,
            [],
        )


def _archive_source_file(
    db: Session,
    job: ImportJob,
    source_file: SourceFile,
    feedback: dict[str, Any],
    *,
    module_registrations: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    archive = auto_archive_draft(
        db,
        source_file,
        feedback,
        module_registrations=module_registrations,
        source_type=job.source_type,
        job=job,
    )
    db.flush()
    return archive


def _load_document_type_hints(source_file: SourceFile) -> list[str]:
    if not source_file.notes:
        return []
    try:
        parsed = json.loads(source_file.notes)
        if isinstance(parsed, dict):
            hints = parsed.get("document_type_hints")
            if isinstance(hints, list):
                return [str(item) for item in hints if item]
    except json.JSONDecodeError:
        pass
    return []


def _process_ai_register_file(db: Session, job: ImportJob, source_file: SourceFile) -> ProcessingResult:
    """AI 路径：原始资料识别并登记到功能模块台账（非会计分录）。"""
    try:
        hints = _load_document_type_hints(source_file)
        classification, ingestion = classify_and_ingest_register(
            db,
            job.organization_id,
            source_file,
            document_type_hints=hints or None,
        )
        feedback = _extract_source_summary(classification)
        feedback.update(
            {
                "register_type": ingestion.document_type,
                "module_label": ingestion.module_label,
                "module_path": ingestion.module_path,
                "register_ids": ingestion.register_ids,
                "register_count": ingestion.register_count,
                "register_summary": ingestion.summary,
                "module_registrations": [
                    {
                        "module_key": item.module_key,
                        "module_label": item.module_label,
                        "module_path": item.module_path,
                        "register_ids": item.register_ids,
                        "register_count": item.register_count,
                        "accounting_dimension": item.accounting_dimension,
                        "semantic_only": item.semantic_only,
                        "reason": item.reason,
                    }
                    for item in ingestion.module_registrations
                ],
                "semantic_decomposition": ingestion.semantic_decomposition,
                "semantic_tags": ingestion.semantic_tags,
                "risk_hints": ingestion.risk_hints,
                "draft_only": ingestion.draft_only,
                "output_path": "register_ledger",
            }
        )
        archive = _archive_source_file(db, job, source_file, feedback)
        feedback["archive"] = archive
        _save_parse_feedback(source_file, feedback, None)
        source_file.text_extract_status = "register_ingested"
        return ProcessingResult(
            file_type="register_ledger",
            filename=source_file.filename,
            success=True,
            register_type=ingestion.document_type,
            register_count=ingestion.register_count,
            register_ids=ingestion.register_ids,
            module_label=ingestion.module_label,
            module_path=ingestion.module_path,
            module_registrations=[item.to_dict() for item in ingestion.module_registrations],
            semantic_decomposition=ingestion.semantic_decomposition,
            semantic_tags=ingestion.semantic_tags,
            risk_hints=ingestion.risk_hints,
            draft_only=ingestion.draft_only,
            archive_path=archive.get("archive_path"),
            archive_context=archive,
        )
    except Exception as exc:
        return ProcessingResult(
            file_type="register_ledger",
            filename=source_file.filename,
            success=False,
            error_message=str(exc),
        )


def _process_structured_preview(db: Session, job: ImportJob, source_file: SourceFile) -> ProcessingResult:
    """
    AI 路径下的结构化文件预览：解析但不落库，引导用户使用序时簿导入模式。
    """
    try:
        parse_result = parse_entries(resolve_storage_path(source_file.storage_path))
        entry_count = len(parse_result.entries)
        if entry_count == 0:
            _save_parse_feedback(
                source_file,
                {
                    "document_type": "structured_ledger",
                    "document_type_label": "结构化序时簿/凭证表",
                    "confidence": 0.0,
                    "summary": "文件为表格格式但未识别到有效分录，请检查列名或改用序时簿导入模式",
                    "voucher_date": None,
                    "amount": None,
                    "counterparty": None,
                    "error_message": "未解析到有效分录数据",
                    "entry_count": 0,
                    "recommended_mode": "day_book_import",
                },
                None,
            )
            source_file.text_extract_status = "structured_preview"
            diagnostics = build_parse_diagnostics(parse_result)
            return ProcessingResult(
                file_type="structured_preview",
                filename=source_file.filename,
                success=False,
                error_message="未解析到有效分录数据",
                parse_diagnostics=diagnostics,
                recommended_mode="day_book_import",
                template_name=parse_result.template_name,
            )

        sample_dates = [entry.get("voucher_date") for entry in parse_result.entries if entry.get("voucher_date")]
        preview_summary = (
            f"识别到 {entry_count} 条结构化分录"
            + (f"，样例日期 {sample_dates[0]}" if sample_dates else "")
            + "。请使用「序时簿导入」模式生成正式会计凭证。"
        )
        feedback = {
            "document_type": "structured_ledger",
            "document_type_label": "结构化序时簿/凭证表",
            "confidence": 1.0,
            "summary": preview_summary,
            "voucher_date": sample_dates[0] if sample_dates else None,
            "amount": None,
            "counterparty": None,
            "entry_count": entry_count,
            "recommended_mode": "day_book_import",
            "recommended_source_type": "ledger_day_book",
        }
        archive = _archive_source_file(db, job, source_file, feedback)
        feedback["archive"] = archive
        _save_parse_feedback(source_file, feedback, None)
        source_file.text_extract_status = "structured_preview"
        return ProcessingResult(
            file_type="structured_preview",
            filename=source_file.filename,
            success=True,
            entries_created=entry_count,
            template_name=parse_result.template_name,
            quality_score=parse_result.quality_score,
            archive_path=archive.get("archive_path"),
            archive_context=archive,
            recommended_mode="day_book_import",
            parse_diagnostics=build_parse_diagnostics(parse_result),
        )
    except Exception as exc:
        _save_parse_feedback(
            source_file,
            {
                "document_type": "structured_ledger",
                "document_type_label": "结构化序时簿/凭证表",
                "confidence": 0.0,
                "summary": "结构化文件解析失败，请检查格式或改用序时簿导入模式",
                "voucher_date": None,
                "amount": None,
                "counterparty": None,
                "error_message": str(exc),
                "recommended_mode": "day_book_import",
            },
            None,
        )
        source_file.text_extract_status = "structured_preview"
        return ProcessingResult(
            file_type="structured_preview",
            filename=source_file.filename,
            success=False,
            error_message=str(exc),
            recommended_mode="day_book_import",
        )


def _extract_text_with_ocr(path: str) -> str:
    """
    功能描述：增强版文本提取，支持 PDF OCR 及多种文档格式
    业务逻辑：
        1. 对 PDF 文件，先尝试常规提取；若内容为空或极少，则使用 OCR
        2. 对 .md 文件，直接读取文本
        3. 对 .doc/.docx 文件，尝试使用 python-docx 提取
    会计口径：文本提取仅用于审计底稿归档和 AI 识别，不影响金额精度
    """
    file_path = Path(path)
    suffix = file_path.suffix.lower()

    # Markdown 文件直接读取
    if suffix == ".md":
        return file_path.read_text(encoding="utf-8", errors="ignore")

    # Word 文档处理
    if suffix in {".doc", ".docx"}:
        try:
            import docx
            doc = docx.Document(file_path)
            return "\n".join(p.text for p in doc.paragraphs if p.text)
        except Exception:
            return ""

    # PDF 处理：先常规提取，再 OCR 兜底
    if suffix == ".pdf":
        try:
            import pdfplumber

            with pdfplumber.open(file_path) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                # 如果提取到的文本极少（少于 50 个字符），认为是纯图片型 PDF，尝试 OCR
                if len(text.strip()) < 50:
                    try:
                        from pdf2image import convert_from_path
                        import pytesseract

                        images = convert_from_path(file_path, dpi=200)
                        ocr_texts = []
                        for img in images:
                            page_text = pytesseract.image_to_string(img, lang="chi_sim+eng")
                            ocr_texts.append(page_text)
                        text = "\n".join(ocr_texts)
                    except Exception:
                        pass
                return text
        except Exception:
            return ""

    # 图片 OCR（复用已有服务）
    if suffix in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}:
        from app.services.ocr_service import extract_text_from_image
        return extract_text_from_image(path)

    return ""


def _process_source_file(db: Session, job: ImportJob, source_file: SourceFile) -> ProcessingResult:
    """
    处理原始文件：
    - 上传时只做文本提取与归档
    - 不直接生成会计分录，等待 AI 识别后走 register_ingestion 或 day_book 流程
    """
    try:
        path = resolve_storage_path(source_file.storage_path)
        raw_text = extract_text(path)
        if not raw_text:
            raw_text = _extract_text_with_ocr(path)

        classification = classify_document(raw_text[:3000], source_file.filename)
        feedback = _extract_source_summary(classification)
        feedback.update({
            "source_type": "source_file",
            "extraction_method": "text_extraction",
            "text_length": len(raw_text),
            "confidence": classification.confidence,
        })

        archive = _archive_source_file(db, job, source_file, feedback)
        feedback["archive"] = archive
        _save_parse_feedback(source_file, feedback, raw_text)
        source_file.text_extract_status = "text_extracted"

        return ProcessingResult(
            file_type="source_file",
            filename=source_file.filename,
            success=True,
            text_extracted=raw_text,
            archive_path=archive.get("archive_path"),
            archive_context=archive,
        )
    except Exception as exc:
        return ProcessingResult(
            file_type="source_file",
            filename=source_file.filename,
            success=False,
            error_message=str(exc),
        )


def process_import_job(
    db: Session,
    job: ImportJob,
    *,
    use_day_book: bool = False,
    accounting_judgment_policy: str = "compliant_default",
) -> ImportReport:
    """处理导入任务

    功能描述：处理导入任务中的所有文件，生成会计分录或 AI 台账
    业务逻辑：
        1. 获取导入任务下的所有文件
        2. 根据文件类型选择处理方式：
           - 会计凭证文件 -> 直接解析并创建分录
           - 原始文件 -> 提取文本并归档（AI 后续处理）
        3. 生成导入报告

    Args:
        db: 数据库会话
        job: 导入任务
        use_day_book: 是否使用序时簿模式
        accounting_judgment_policy: 会计判断策略

    Returns:
        ImportReport: 导入报告
    """
    if use_day_book or is_day_book_source_type(job.source_type):
        return _process_import_job_as_day_book(db, job)

    source_files = db.query(SourceFile).filter(SourceFile.import_job_id == job.id).all()

    total_entries = 0
    success_files = 0
    failed_files = 0
    file_results: list[ProcessingResult] = []
    all_tags: list[str] = []
    all_logic_results: list[Any] = []
    all_parse_entries: list[dict[str, Any]] = []

    for source_file in source_files:
        file_type = Path(source_file.filename or "").suffix.lower()

        if job.source_type in AI_EVIDENCE_SOURCE_TYPES:
            result = _process_ai_register_file(db, job, source_file)
            file_results.append(result)
            if result.success:
                success_files += 1
            else:
                failed_files += 1
        elif _is_accounting_file(file_type) and should_persist_structured_entries(job.source_type):
            result, tags, logic_report, parse_entries = _process_accounting_file(db, job, source_file)
            file_results.append(result)
            if result.success:
                success_files += 1
                total_entries += result.entries_created
                all_tags.extend(tags)
                if logic_report:
                    all_logic_results.append(logic_report)
                all_parse_entries.extend(parse_entries)
            else:
                failed_files += 1

        elif _is_source_file(file_type):
            result = _process_source_file(db, job, source_file)
            file_results.append(result)
            if result.success:
                success_files += 1
            else:
                failed_files += 1

        else:
            file_results.append(ProcessingResult(
                file_type="unknown",
                filename=source_file.filename,
                success=False,
                error_message=f"不支持的文件类型：{file_type}",
            ))
            failed_files += 1

    # 合并逻辑校验报告
    merged_logic_report: BatchCheckReport | None = None
    if all_logic_results:
        merged_entries = []
        for report in all_logic_results:
            merged_entries.extend(report.entries)
        merged_logic_report = generate_batch_report(merged_entries)

    # 生成质量报告
    quality_report = generate_quality_report(
        [entry for entry in all_parse_entries],
        [r for r in file_results if r.success],
    )

    if failed_files == 0 and success_files > 0:
        if total_entries > 0:
            job.status = "completed"
            job.entry_count = total_entries
        elif job.source_type in AI_EVIDENCE_SOURCE_TYPES:
            job.status = "parsed"
        db.commit()

    return ImportReport(
        job_id=job.id,
        total_files=len(source_files),
        success_files=success_files,
        failed_files=failed_files,
        total_entries=total_entries,
        file_results=file_results,
        logic_report=merged_logic_report,
        quality_report=quality_report,
    )


def _process_import_job_as_day_book(db: Session, job: ImportJob) -> ImportReport:
    """使用序时簿模式处理导入任务。"""
    source_files = db.query(SourceFile).filter(SourceFile.import_job_id == job.id).all()
    file_results: list[ProcessingResult] = []
    total_entries = 0
    success_files = 0
    failed_files = 0

    try:
        day_result: DayBookProcessingResult = process_day_book_import(db, job)

        for source_file in source_files:
            file_type = Path(source_file.filename or "").suffix.lower()
            if not (_is_accounting_file(file_type) or should_persist_structured_entries(job.source_type)):
                continue

            file_results.append(ProcessingResult(
                file_type="accounting_entry",
                filename=source_file.filename,
                success=day_result.success,
                entries_created=day_result.entries_created if day_result.success else 0,
                error_message=day_result.error_message,
            ))

        if day_result.success:
            success_files = len(file_results)
            total_entries = day_result.entries_created
            job.status = "completed"
            job.entry_count = total_entries
            db.commit()
        else:
            failed_files = len(file_results)

        return ImportReport(
            job_id=job.id,
            total_files=len(source_files),
            success_files=success_files,
            failed_files=failed_files,
            total_entries=total_entries,
            file_results=file_results,
            day_book_report=day_result.report,
        )
    except Exception as exc:
        for source_file in source_files:
            file_type = Path(source_file.filename or "").suffix.lower()
            if not (_is_accounting_file(file_type) or should_persist_structured_entries(job.source_type)):
                continue

            file_results.append(ProcessingResult(
                file_type="accounting_entry",
                filename=source_file.filename,
                success=False,
                error_message=str(exc),
            ))
            failed_files += 1

        return ImportReport(
            job_id=job.id,
            total_files=len(source_files),
            success_files=0,
            failed_files=failed_files,
            total_entries=0,
            file_results=file_results,
            day_book_report=None,
        )


def get_import_summary(report: ImportReport) -> dict[str, Any]:
    """将 ImportReport 转换为前端可读的摘要字典。"""
    return {
        "job_id": report.job_id,
        "total_files": report.total_files,
        "success_files": report.success_files,
        "failed_files": report.failed_files,
        "total_entries": report.total_entries,
        "output_path": report.output_path,
        "period_suggestion": report.period_suggestion,
        "register_summary": report.register_summary,
        "quality_score": report.quality_report.quality_score if report.quality_report else 0.0,
        "logic_check_error_count": report.logic_report.error_count if report.logic_report else 0,
        "file_results": [
            {
                "file_type": r.file_type,
                "filename": r.filename,
                "success": r.success,
                "entries_created": r.entries_created,
                "error_message": r.error_message,
                "template_name": r.template_name,
                "quality_score": r.quality_score,
                "register_type": r.register_type,
                "register_count": r.register_count,
                "module_label": r.module_label,
                "module_path": r.module_path,
                "archive_path": r.archive_path,
                "recommended_mode": r.recommended_mode,
            }
            for r in report.file_results
        ],
    }


def generate_import_report(
    db: Session,
    job: ImportJob,
    *,
    accounting_judgment_policy: str = "compliant_default",
) -> ImportReport:
    """生成导入报告"""
    report = process_import_job(
        db,
        job,
        use_day_book=is_day_book_source_type(job.source_type),
        accounting_judgment_policy=accounting_judgment_policy,
    )
    return report
