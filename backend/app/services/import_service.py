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
from app.storage.local_storage import save_upload


# 会计凭证文件类型
ACCOUNTING_FILE_TYPES = {".xlsx", ".xls", ".csv"}

# 原始文件类型
SOURCE_FILE_TYPES = {".pdf", ".txt", ".md", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}

DOCUMENT_TYPE_LABELS = {
    "invoice": "发票",
    "bank_statement": "银行流水",
    "contract": "合同",
    "inventory_receipt": "入库单",
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
        industry: 行业类型
        fiscal_year: 会计年度
        source_type: 数据来源类型，默认 "voucher_import"，可选 "audit_day_book"

    Returns:
        ImportJob: 创建的导入任务对象
    """
    organization = None
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

    # 【修复】自动关联账套ID：如果 job 没有 ledger_id，尝试从同 organization 的其他 job 获取
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


def _process_accounting_file(db: Session, job: ImportJob, source_file: SourceFile) -> tuple[ProcessingResult, list[dict], BatchCheckReport | None]:
    """
    处理会计凭证文件

    流程：
    1. 解析文件（自适应模板匹配）
    2. 生成多维度 tags
    3. 逻辑校验（摘要-科目匹配）
    4. 风险案例匹配
    5. 创建分录
    6. 向量索引
    """
    try:
        # 解析文件
        parse_result = parse_entries(source_file.storage_path)

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
                [],  # 返回空分录列表
            )

        # 收集用于逻辑校验的数据
        entries_for_check: list[dict] = []
        voucher_types: list[str | None] = []

        for entry_data in parse_result.entries:
            # 提取凭证字
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

            # 构建用于校验的数据
            entries_for_check.append({
                "summary": entry_data.get("summary", ""),
                "debit_account": entry_data.get("debit_account_name", ""),
                "credit_account": entry_data.get("credit_account_name", ""),
                "debit_amount": entry_data.get("debit_amount", 0),
                "credit_amount": entry_data.get("credit_amount", 0),
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

        # 创建分录
        entries_created = 0
        voucher_line_counter: dict[str, int] = {}
        for i, entry_data in enumerate(parse_result.entries):
            # 生成多维度 tags
            tags = generate_entry_tags(entry_data)

            # 增强分录（添加风险案例匹配）
            entry_data["tags"] = tags
            entry_data = enhance_entry_with_risk_analysis(entry_data)

            # 构建语义文本（用于向量化）
            semantic_text = build_semantic_text(entry_data, tags)

            # 同凭证号下分配连续行号；缺少凭证号时该分录独立分组
            voucher_no = entry_data.get("voucher_no") or f"__no_voucher__:{i}"
            voucher_line_counter[voucher_no] = voucher_line_counter.get(voucher_no, 0) + 1
            entry_data["entry_line_no"] = voucher_line_counter[voucher_no]

            # 仅保留 AccountingEntry 模型字段，避免传入 tags / risk_cases 等扩展字段
            model_fields = {
                "voucher_no",
                "voucher_date",
                "summary",
                "account_code",
                "account_name",
                "debit_amount",
                "credit_amount",
                "counterparty",
                "original_row",
                "normalized_text",
                "entry_line_no",
            }
            entry_kwargs = {k: v for k, v in entry_data.items() if k in model_fields}
            # 【新增】设置分录来源标记：自动导入 + 关联源文件
            entry_kwargs["entry_source"] = "auto"
            entry_kwargs["source_file_id"] = source_file.id
            entry_kwargs["ledger_id"] = source_file.ledger_id
            entry = AccountingEntry(organization_id=job.organization_id, import_job_id=job.id, **entry_kwargs)
            db.add(entry)
            db.flush()

            # 保存 tags 到 EntryTag
            for tag in tags:
                db.add(EntryTag(entry_id=entry.id, tag_name=tag, confidence=1.0))

            # 保存逻辑校验结果到 tags
            check_result = logic_check_results[i]
            if not check_result.is_consistent:
                for issue in check_result.issues:
                    tag_name = f"逻辑校验:{issue.severity}:{issue.issue_type}"
                    db.add(EntryTag(entry_id=entry.id, tag_name=tag_name, confidence=0.9))

            # 保存风险案例匹配结果
            for case in check_result.matched_risk_cases:
                tag_name = f"风险案例:{case['risk_type']}:{case['id']}"
                db.add(EntryTag(entry_id=entry.id, tag_name=tag_name, confidence=0.9))

            # 向量索引（使用增强的语义文本）
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
                    "tags": tags,
                    "is_consistent": check_result.is_consistent,
                    "risk_count": len(check_result.matched_risk_cases),
                },
            )
            entries_created += 1

        first_entry = parse_result.entries[0] if parse_result.entries else {}
        archive_feedback = {
            "document_type": "structured_ledger" if is_day_book_source_type(job.source_type) else "accounting_voucher",
            "document_type_label": "序时簿" if is_day_book_source_type(job.source_type) else "会计凭证",
            "voucher_date": first_entry.get("voucher_date"),
            "summary": f"解析 {entries_created} 条分录",
        }
        archive = _archive_source_file(db, job, source_file, archive_feedback)

        # 更新文件状态
        source_file.text_extract_status = "parsed_entries"
        source_file.extracted_text = f"解析成功：{parse_result.template_name or '未知模板'}，{entries_created}条分录，逻辑校验问题{logic_report.error_count}个"

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
            tags,
            logic_report,
            parse_result.entries,  # 返回解析的分录列表，避免重复解析
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
            [],  # 返回空列表
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
        if ingestion.error_message:
            feedback["error_message"] = ingestion.error_message

        module_regs = [
            {
                "module_key": item.module_key,
                "module_label": item.module_label,
                "semantic_only": item.semantic_only,
            }
            for item in ingestion.module_registrations
        ]
        archive = _archive_source_file(db, job, source_file, feedback, module_registrations=module_regs)
        feedback["archive"] = archive

        raw_text = classification.raw_text or extract_text(source_file.storage_path) or ""
        _save_parse_feedback(source_file, feedback, raw_text)
        source_file.text_extract_status = "register_ingested" if ingestion.success else "extracted"

        if raw_text:
            _index_text(
                db,
                job.organization_id,
                "source_file_chunk",
                source_file.id,
                raw_text,
                {
                    "organization_id": job.organization_id,
                    "import_job_id": job.id,
                    "filename": source_file.filename,
                    "register_type": ingestion.document_type,
                },
            )

        return ProcessingResult(
            file_type="register_ledger",
            filename=source_file.filename,
            success=ingestion.success,
            text_extracted=raw_text[:200] + "..." if len(raw_text) > 200 else raw_text,
            register_type=ingestion.document_type,
            register_count=ingestion.register_count,
            register_ids=ingestion.register_ids,
            module_label=ingestion.module_label,
            module_path=ingestion.module_path,
            module_registrations=[
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
            semantic_decomposition=ingestion.semantic_decomposition,
            semantic_tags=ingestion.semantic_tags,
            risk_hints=ingestion.risk_hints,
            draft_only=ingestion.draft_only,
            error_message=ingestion.error_message,
            archive_path=archive.get("archive_path"),
            archive_context=archive,
        )
    except Exception as exc:
        source_file.text_extract_status = "failed"
        _save_parse_feedback(
            source_file,
            {
                "document_type": "unknown",
                "document_type_label": "台账登记失败",
                "confidence": 0.0,
                "summary": "文件已保存为底稿，但 AI 台账登记失败",
                "error_message": str(exc),
                "output_path": "register_ledger",
            },
            "",
        )
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
        parse_result = parse_entries(source_file.storage_path)
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

    # 纯文本
    if suffix in {".txt", ".csv"}:
        return file_path.read_text(encoding="utf-8", errors="ignore")

    return ""


def _is_image_only_pdf(path: str) -> bool:
    """
    功能描述：判断 PDF 是否为纯图片型（无文字层）
    业务逻辑：提取文本后若内容极少，则判定为纯图片型
    """
    try:
        import pdfplumber

        with pdfplumber.open(path) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            return len(text.strip()) < 50
    except Exception:
        return False


def _process_source_file(db: Session, job: ImportJob, source_file: SourceFile) -> ProcessingResult:
    """
    处理原始文件

    流程：
    1. 提取文本（PDF/TXT/图片OCR/Word/Markdown）
    2. 合同解析（如果是PDF合同文件）
    3. 向量索引
    """
    try:
        # 提取文本（使用增强版提取器）
        text = _extract_text_with_ocr(source_file.storage_path)

        if not text:
            source_file.text_extract_status = "unsupported"
            _save_parse_feedback(
                source_file,
                {
                    "document_type": "unknown",
                    "document_type_label": "无法确认",
                    "confidence": 0.0,
                    "summary": "系统未能确认该文件资料类型，请检查文件内容或补充资料类型说明",
                    "voucher_date": None,
                    "amount": None,
                    "counterparty": None,
                    "error_message": "无法提取文本内容",
                },
                "",
            )
            return ProcessingResult(
                file_type="source_file",
                filename=source_file.filename,
                success=False,
                error_message="无法提取文本内容",
            )

        # 合同解析：如果是PDF文件且内容像合同，进行结构化解析
        contract_parse_result = None
        if source_file.file_type.lower() == ".pdf" and _is_contract_text(text):
            try:
                from app.services.contract_parser_service import ContractParser
                parser = ContractParser()
                contract_parse_result = parser.parse(text)
                # 保存合同解析结果到draft_data
                if job.draft_data is None:
                    job.draft_data = {}
                job.draft_data["contract_parse_result"] = {
                    "contract_type": contract_parse_result.contract_type,
                    "parties": [
                        {
                            "name": p.name,
                            "role": p.role,
                            "tax_id": p.tax_id,
                        }
                        for p in contract_parse_result.parties
                    ],
                    "signing_date": contract_parse_result.signing_date,
                    "period": {
                        "start_date": contract_parse_result.period.start_date,
                        "end_date": contract_parse_result.period.end_date,
                        "duration_days": contract_parse_result.period.duration_days,
                    },
                    "price": {
                        "total_amount": str(contract_parse_result.price.total_amount),
                        "tax_rate": str(contract_parse_result.price.tax_rate),
                        "tax_amount": str(contract_parse_result.price.tax_amount),
                        "amount_excl_tax": str(contract_parse_result.price.amount_excl_tax),
                        "currency": contract_parse_result.price.currency,
                        "payment_terms": contract_parse_result.price.payment_terms,
                    },
                    "items": [
                        {
                            "item_no": i.item_no,
                            "description": i.description,
                            "quantity": str(i.quantity),
                            "unit": i.unit,
                            "unit_price": str(i.unit_price),
                            "total_price": str(i.total_price),
                            "revenue_recognition_method": i.revenue_recognition_method,
                            "performance_obligations": i.performance_obligations,
                        }
                        for i in contract_parse_result.items
                    ],
                    "penalties": [
                        {
                            "penalty_clause": p.penalty_clause,
                            "penalty_amount": str(p.penalty_amount),
                            "is_probable": p.is_probable,
                            "provision_required": p.provision_required,
                            "provision_amount": str(p.provision_amount),
                            "impact_on_revenue": p.impact_on_revenue,
                        }
                        for p in contract_parse_result.penalties
                    ],
                    "summary": contract_parse_result.summary,
                    "accounting_notes": contract_parse_result.accounting_notes,
                    "confidence_score": str(contract_parse_result.confidence_score),
                }
                # 进行会计校验
                validation_errors = parser.validate_accounting(contract_parse_result)
                if validation_errors:
                    job.draft_data["contract_validation_errors"] = validation_errors
            except Exception as e:
                # 合同解析失败不影响主流程，记录错误即可
                print(f"合同解析失败: {e}")

        result = classify_document(source_file.storage_path, source_file.filename)
        feedback = _extract_source_summary(result)

        # 如果合同解析成功，增强反馈信息
        if contract_parse_result and contract_parse_result.confidence_score > 0.5:
            feedback["contract_info"] = {
                "contract_type": contract_parse_result.contract_type,
                "parties": [p.name for p in contract_parse_result.parties],
                "total_amount": str(contract_parse_result.price.total_amount),
                "signing_date": contract_parse_result.signing_date,
                "accounting_notes": contract_parse_result.accounting_notes,
            }

        archive = _archive_source_file(db, job, source_file, feedback)
        feedback["archive"] = archive

        # 更新文件状态
        _save_parse_feedback(source_file, feedback, result.raw_text or text)
        source_file.text_extract_status = "extracted"

        # 向量索引
        _index_text(
            db,
            job.organization_id,
            "source_file_chunk",
            source_file.id,
            text,
            {
                "organization_id": job.organization_id,
                "import_job_id": job.id,
                "filename": source_file.filename,
            },
        )

        return ProcessingResult(
            file_type="source_file",
            filename=source_file.filename,
            success=True,
            text_extracted=text[:200] + "..." if len(text) > 200 else text,
            archive_path=archive.get("archive_path"),
            archive_context=archive,
        )

    except Exception as exc:
        source_file.text_extract_status = "failed"
        _save_parse_feedback(
            source_file,
            {
                "document_type": "unknown",
                "document_type_label": "解析失败",
                "confidence": 0.0,
                "summary": "文件上传成功但解析失败，请重新上传、改为人工录入或继续补充其他资料",
                "voucher_date": None,
                "amount": None,
                "counterparty": None,
                "error_message": str(exc),
            },
            "",
        )
        return ProcessingResult(
            file_type="source_file",
            filename=source_file.filename,
            success=False,
            error_message=str(exc),
        )


def _is_contract_text(text: str) -> bool:
    """
    判断文本是否为合同内容

    功能描述：通过关键词匹配判断文本是否为合同
    业务逻辑：
        1. 检查是否包含合同关键词（甲方、乙方、合同、协议等）
        2. 检查是否包含合同条款（违约责任、付款方式等）
        3. 综合判断置信度

    Args:
        text: 提取的文本内容

    Returns:
        bool: 是否为合同文本
    """
    contract_keywords = [
        "甲方", "乙方", "丙方", "合同", "协议", "签约",
        "违约", "付款", "价款", "金额", "税率", "含税",
        "履行", "标的", "交付", "验收", "质保",
    ]
    text_lower = text.lower()
    keyword_count = sum(1 for keyword in contract_keywords if keyword in text_lower)
    # 至少匹配3个关键词才认为是合同
    return keyword_count >= 3



def process_import_job(db: Session, job: ImportJob) -> ImportReport:
    """
    处理导入任务

    支持两种文件类型分别处理：
    - 会计凭证文件 (.xlsx, .xls, .csv) → 解析分录
    - 原始文件 (.pdf, .txt, .md, .doc, .docx, 图片) → 提取文本

    支持两种数据来源模式：
    - voucher_import（默认）：标准凭证导入模式
    - audit_day_book：审计序时簿模式，增加凭证合并、借贷平衡校验、跳号检测

    集成功能：
    - 多维度 tags 语义标签
    - 逻辑校验（摘要-科目匹配）
    - 风险案例匹配
    - 解析超时保护（30 秒）
    - PDF OCR 支持（纯图片型 PDF 自动识别）
    """
    job.status = "processing"
    job.error_message = None
    db.commit()

    output_path = get_import_output_path(job.source_type)

    # 超时保护：30 秒超时后自动设置为 draft
    timeout_occurred = False
    timeout_error = ""

    def _on_timeout():
        nonlocal timeout_occurred, timeout_error
        timeout_occurred = True
        timeout_error = "解析超时：文件处理时间超过 30 秒，已保存为草稿供后续重试"
        try:
            job.status = "draft"
            job.error_message = timeout_error
            job.draft_data = {
                "stage": "parse_timeout",
                "error_message": timeout_error,
                "failed_at": datetime.utcnow().isoformat(),
                "request_id": f"draft-{job.id}-{int(datetime.utcnow().timestamp())}",
            }
            db.commit()
        except Exception:
            pass

    timer = threading.Timer(30.0, _on_timeout)
    timer.start()

    try:
        # 序时簿模式（审计 / 记账）：调用专用处理逻辑
        if is_day_book_source_type(job.source_type):
            day_book_result = process_day_book_import(db, job)
            if not day_book_result.success:
                job.status = "failed"
                job.error_message = day_book_result.error_message
                db.commit()
                timer.cancel()
                return ImportReport(
                    job_id=job.id,
                    total_files=0,
                    success_files=0,
                    failed_files=1,
                    total_entries=0,
                    output_path=output_path,
                    error_message=day_book_result.error_message,
                    parse_diagnostics=day_book_result.parse_diagnostics,
                    file_results=[
                        ProcessingResult(
                            file_type="accounting_entry",
                            filename=job.source_type,
                            success=False,
                            error_message=day_book_result.error_message or "序时簿处理失败",
                            parse_diagnostics=day_book_result.parse_diagnostics,
                            recommended_mode="day_book_import",
                        )
                    ],
                )

            job.entry_count = day_book_result.entries_created
            job.status = "completed"
            db.commit()
            timer.cancel()

            period_suggestion = None
            if day_book_result.entries_created > 0:
                generate_risks(db, job.id)
                period_suggestion = suggest_period_for_job(db, job.id, job.organization_id)

            return ImportReport(
                job_id=job.id,
                total_files=1,
                success_files=1,
                failed_files=0,
                total_entries=day_book_result.entries_created,
                output_path=output_path,
                period_suggestion=period_suggestion,
                day_book_report=day_book_result.report,
                file_results=[
                    ProcessingResult(
                        file_type="accounting_entry",
                        filename=job.source_type,
                        success=True,
                        entries_created=day_book_result.entries_created,
                    )
                ],
            )

        file_results: list[ProcessingResult] = []
        total_entries = 0
        all_entries: list[dict[str, Any]] = []
        all_tags: list[str] = []
        logic_reports: list[BatchCheckReport] = []

        try:
            files = db.query(SourceFile).filter(SourceFile.import_job_id == job.id).all()

            for source_file in files:
                file_type = source_file.file_type.lower()

                # 根据文件类型选择处理方式
                if _is_accounting_file(file_type):
                    if job.source_type in AI_EVIDENCE_SOURCE_TYPES:
                        result = _process_structured_preview(db, job, source_file)
                        file_results.append(result)
                        continue

                    if not should_persist_structured_entries(job.source_type):
                        result = _process_structured_preview(db, job, source_file)
                        file_results.append(result)
                        continue

                    result, tags, logic_report, parsed_entries = _process_accounting_file(db, job, source_file)
                    total_entries += result.entries_created
                    file_results.append(result)
                    all_tags.extend(tags)
                    if logic_report:
                        logic_reports.append(logic_report)

                    # 复用解析的分录，避免重复解析
                    if parsed_entries:
                        all_entries.extend(parsed_entries)

                elif _is_source_file(file_type):
                    if job.source_type in AI_EVIDENCE_SOURCE_TYPES:
                        result = _process_ai_register_file(db, job, source_file)
                    else:
                        result = _process_source_file(db, job, source_file)
                    file_results.append(result)

                else:
                    # 不支持的文件格式，返回友好错误信息
                    supported_formats = ", ".join(
                        sorted(
                            ACCOUNTING_FILE_TYPES | SOURCE_FILE_TYPES
                        )
                    )
                    friendly_error = (
                        f"不支持的文件类型: {file_type}。"
                        f"当前支持的格式包括：{supported_formats}。"
                        f"请转换格式后重新上传，或联系管理员处理。"
                    )
                    result = ProcessingResult(
                        file_type="unknown",
                        filename=source_file.filename,
                        success=False,
                        error_message=friendly_error,
                    )
                    file_results.append(result)

            # 生成质量报告（仅针对会计分录）
            quality_report = None
            if all_entries:
                quality_report = generate_quality_report(all_entries)

            # 合并逻辑校验报告
            combined_logic_report = None
            if logic_reports:
                total_errors = sum(r.error_count for r in logic_reports)
                total_warnings = sum(r.warning_count for r in logic_reports)
                total_inconsistent = sum(r.inconsistent_entries for r in logic_reports)
                combined_logic_report = {
                    "total_errors": total_errors,
                    "total_warnings": total_warnings,
                    "total_inconsistent": total_inconsistent,
                    "consistency_rate": (len(all_entries) - total_inconsistent) / max(len(all_entries), 1) * 100 if all_entries else 0,
                }

            # 更新任务状态
            job.entry_count = total_entries
            success_files = sum(1 for r in file_results if r.success)
            failed_files = len(file_results) - success_files
            report_error_message: str | None = None
            report_parse_diagnostics: dict[str, Any] | None = None
            report_output_path = output_path

            structured_previews = [r for r in file_results if r.file_type == "structured_preview"]
            if structured_previews:
                report_output_path = "structured_preview"
                failed_structured = [r for r in structured_previews if not r.success]
                if failed_structured:
                    # 解析失败时保存草稿数据，进入 draft 状态供用户重试
                    job.status = "draft"
                    report_error_message = failed_structured[0].error_message
                    report_parse_diagnostics = failed_structured[0].parse_diagnostics
                    job.error_message = report_error_message
                    job.draft_data = {
                        "stage": "structured_preview_failed",
                        "file_results": [{
                            "filename": r.filename,
                            "success": r.success,
                            "error_message": r.error_message,
                            "parse_diagnostics": r.parse_diagnostics,
                            "entries_created": r.entries_created,
                        } for r in file_results],
                        "total_entries": total_entries,
                        "failed_at": datetime.utcnow().isoformat(),
                        "request_id": f"draft-{job.id}-{int(datetime.utcnow().timestamp())}",
                    }
                else:
                    job.status = "completed"
            elif failed_files > 0 and total_entries == 0:
                # 所有文件解析失败，保存草稿数据进入 draft 状态
                job.status = "draft"
                report_error_message = next((r.error_message for r in file_results if r.error_message), "导入处理失败")
                job.error_message = report_error_message
                job.draft_data = {
                    "stage": "all_files_failed",
                    "file_results": [{
                        "filename": r.filename,
                        "success": r.success,
                        "error_message": r.error_message,
                        "parse_diagnostics": r.parse_diagnostics,
                        "entries_created": r.entries_created,
                    } for r in file_results],
                    "total_entries": total_entries,
                    "failed_at": datetime.utcnow().isoformat(),
                    "request_id": f"draft-{job.id}-{int(datetime.utcnow().timestamp())}",
                }
            else:
                job.status = "completed"

            # 生成风险
            if total_entries > 0:
                generate_risks(db, job.id)

            db.commit()

            period_suggestion = None
            if total_entries > 0 and is_day_book_source_type(job.source_type):
                period_suggestion = suggest_period_for_job(db, job.id, job.organization_id)

            register_summary = [
                {
                    "filename": item.filename,
                    "register_type": item.register_type,
                    "register_count": item.register_count,
                    "register_ids": item.register_ids,
                    "module_label": item.module_label,
                    "module_path": item.module_path,
                    "module_registrations": item.module_registrations,
                    "semantic_decomposition": item.semantic_decomposition,
                    "semantic_tags": item.semantic_tags,
                    "risk_hints": item.risk_hints,
                    "draft_only": item.draft_only,
                    "success": item.success,
                    "archive_path": item.archive_path,
                    "archive_context": item.archive_context,
                }
                for item in file_results
                if item.file_type == "register_ledger"
            ] or None

            timer.cancel()
            return ImportReport(
                job_id=job.id,
                total_files=len(file_results),
                success_files=success_files,
                failed_files=failed_files,
                total_entries=total_entries,
                output_path=report_output_path,
                period_suggestion=period_suggestion,
                quality_report=quality_report,
                register_summary=register_summary,
                file_results=file_results,
                error_message=report_error_message,
                parse_diagnostics=report_parse_diagnostics,
            )

        except Exception as exc:
            # 如果超时已经发生，使用超时错误信息
            if timeout_occurred:
                job.status = "draft"
                job.error_message = timeout_error
                job.draft_data = {
                    "stage": "parse_timeout",
                    "error_message": timeout_error,
                    "failed_at": datetime.utcnow().isoformat(),
                    "request_id": f"draft-{job.id}-{int(datetime.utcnow().timestamp())}",
                }
            else:
                job.status = "failed"
                job.error_message = str(exc)
            db.commit()
            timer.cancel()

            return ImportReport(
                job_id=job.id,
                total_files=len(file_results),
                success_files=0,
                failed_files=len(file_results),
                total_entries=total_entries,
                output_path=output_path,
                file_results=file_results,
            )

    except Exception as exc:
        # 外层异常处理
        if timeout_occurred:
            job.status = "draft"
            job.error_message = timeout_error
            job.draft_data = {
                "stage": "parse_timeout",
                "error_message": timeout_error,
                "failed_at": datetime.utcnow().isoformat(),
                "request_id": f"draft-{job.id}-{int(datetime.utcnow().timestamp())}",
            }
        else:
            job.status = "failed"
            job.error_message = str(exc)
        db.commit()
        timer.cancel()

        return ImportReport(
            job_id=job.id,
            total_files=0,
            success_files=0,
            failed_files=0,
            total_entries=0,
            output_path=output_path,
            file_results=[],
        )


def get_import_summary(report: ImportReport) -> dict[str, Any]:
    """生成导入摘要"""
    summary = {
        "job_id": report.job_id,
        "total_files": report.total_files,
        "success_files": report.success_files,
        "failed_files": report.failed_files,
        "total_entries": report.total_entries,
        "output_path": report.output_path,
        "file_summary": [],
    }

    if report.error_message:
        summary["error_message"] = report.error_message
    if report.parse_diagnostics is not None:
        summary["parse_diagnostics"] = report.parse_diagnostics

    if report.period_suggestion is not None:
        summary["period_suggestion"] = report.period_suggestion

    if report.register_summary is not None:
        summary["register_summary"] = report.register_summary

    if report.day_book_report is not None:
        report_data = report.day_book_report
        summary["day_book_report"] = {
            "total_vouchers": report_data.total_vouchers,
            "total_entries": report_data.total_entries,
            "skip_count": report_data.skip_count,
            "unbalanced_count": report_data.unbalanced_count,
            "completeness_score": report_data.completeness_score,
            "missing_voucher_nos": report_data.missing_voucher_nos,
            "unbalanced_vouchers": [
                {
                    "voucher_no": item.voucher_no,
                    "debit_total": str(item.debit_total),
                    "credit_total": str(item.credit_total),
                    "difference": str(item.difference),
                    "entry_count": item.entry_count,
                }
                for item in report_data.unbalanced_vouchers
            ],
        }

    for result in report.file_results:
        file_info = {
            "filename": result.filename,
            "type": result.file_type,
            "success": result.success,
        }
        if result.file_type == "accounting_entry":
            file_info["entries"] = result.entries_created
            file_info["template"] = result.template_name
            file_info["quality_score"] = result.quality_score
        if result.file_type == "structured_preview":
            file_info["entries"] = result.entries_created
            file_info["template"] = result.template_name
            file_info["quality_score"] = result.quality_score
        if result.file_type == "register_ledger":
            file_info["register_type"] = result.register_type
            file_info["register_count"] = result.register_count
            file_info["register_ids"] = result.register_ids
            file_info["module_label"] = result.module_label
            file_info["module_path"] = result.module_path
            file_info["module_registrations"] = result.module_registrations
            file_info["draft_only"] = result.draft_only
        if result.error_message:
            file_info["error"] = result.error_message
        if result.recommended_mode:
            file_info["recommended_mode"] = result.recommended_mode
        if result.parse_diagnostics:
            file_info["parse_diagnostics"] = result.parse_diagnostics

        summary["file_summary"].append(file_info)

    # 质量报告
    if report.quality_report:
        summary["quality"] = {
            "overall_score": report.quality_report.overall_score,
            "valid_entries": report.quality_report.valid_entries,
            "invalid_entries": report.quality_report.invalid_entries,
            "recommendations": report.quality_report.recommendations,
        }

    # 逻辑校验报告
    if hasattr(report, "logic_report") and report.logic_report:
        summary["logic_check"] = {
            "total_errors": report.logic_report.error_count,
            "total_warnings": report.logic_report.warning_count,
            "consistency_rate": report.logic_report.consistency_rate,
        }

    return summary
