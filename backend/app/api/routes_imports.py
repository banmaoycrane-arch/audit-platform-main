from typing import Any, Literal
from decimal import Decimal
import json
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.models.user import User
from app.db.models import ImportJob, SourceFile, StagingAccountingEntry
from app.models.project import Project
from app.models.project_ledger import ProjectLedger
from app.models.ledger import Ledger
from app.models.team import Team
from app.models.user_ledger_auth import UserLedgerAuth
from app.db.session import SessionLocal, get_db
from app.schemas.import_job import (
    AuditScopeUpdate,
    DayBookReportRead,
    ImportJobCleanupPayload,
    ImportJobCreate,
    ImportJobRead,
    ParseOptionsUpdate,
)
from app.services.doc_parsing.import_service import (
    attach_file,
    create_import_job,
    get_import_summary,
    process_import_job,
    _process_source_file,
    _process_ai_register_file,
    _is_source_file,
)
from app.services.shared.project_service import get_or_create_unknown_project
from app.services.shared.ledger_context_service import resolve_import_job_ledger_id
from app.services.audit.audit_day_book_service import DayBookReport, process_day_book_import
from app.services.accounting.entry_generation_service import _normalize_evidence_type
from app.services.doc_parsing.import_routing_service import (
    get_import_output_path,
    is_day_book_source_type,
    is_structured_source_type,
    AI_EVIDENCE_SOURCE_TYPES,
)
from app.services.doc_parsing.structured_format_detection_service import detect_structured_file_format
from app.services.audit.structured_import_service import (
    apply_compliance_spot_check,
    apply_compliance_random_sample,
    build_dimension_pending_queue,
    build_staging_dimension_registry,
    bulk_update_dimension_display_name,
    batch_update_preview_review,
    cancel_structured_import,
    confirm_structured_import,
    list_preview_entries,
    get_preview_voucher_review_stats,
    list_preview_vouchers,
    get_preview_voucher_lines,
    review_all_preview_entries,
    update_preview_entry,
)
from app.services.audit.compliance_review_service import (
    iter_staging_compliance_review,
    review_staging_compliance,
)
from app.services.accounting.period_detection_service import (
    apply_import_period_mapping,
    suggest_period_for_job,
)
from app.services.doc_parsing.parser_engine.unified_parser_service import (
    get_latest_source_file,
    mark_missing_source_file,
    mark_parser_engine_failure,
    parse_source_file_with_unified_engine,
)

router = APIRouter(prefix="/api/import-jobs", tags=["import-jobs"])

# 存储最近导入报告（生产环境应存储到数据库）
_import_reports: dict[int, dict[str, Any]] = {}

# 存储序时簿检测报告（生产环境应存储到数据库）
_day_book_reports: dict[int, DayBookReport] = {}


AUDIT_SOURCE_TYPES = {"audit_day_book"}


class ApplyPeriodMappingPayload(BaseModel):
    period_mapping_mode: Literal["preserve_source", "unify_target"]
    period_mode: Literal["adaptive", "fixed"] | None = None
    period_id: int | None = None
    period_start_date: date | None = None
    period_end_date: date | None = None


def _requires_audit_project_context(source_type: str | None, audit_scope_type: str | None = None, project_id: int | None = None) -> bool:
    """是否需要审计项目上下文。"""
    # 只有审计类 source_type 或已关联 project_id 时才需要审计项目上下文
    is_audit_source = source_type in AUDIT_SOURCE_TYPES or bool(source_type and source_type.startswith("audit_"))
    return is_audit_source or bool(project_id)


def _is_enterprise_accountant_context(db: Session, *, user_id: int | None, ledger_id: int | None) -> bool:
    if not user_id or not ledger_id:
        return False
    ledger = db.get(Ledger, ledger_id)
    if not ledger:
        return False
    team = db.get(Team, ledger.team_id)
    if not team or team.type != "enterprise":
        return False
    auth = (
        db.query(UserLedgerAuth)
        .filter(UserLedgerAuth.user_id == user_id, UserLedgerAuth.ledger_id == ledger_id)
        .first()
    )
    return bool(auth and auth.role in {"accountant", "admin"})


def _ensure_project_ledger_context(
    db: Session,
    *,
    project_id: int | None,
    ledger_id: int | None,
    source_type: str | None,
    audit_scope_type: str | None = None,
    user_id: int | None = None,
) -> None:
    if not _requires_audit_project_context(source_type, audit_scope_type, project_id):
        return
    if not ledger_id:
        raise HTTPException(status_code=400, detail="导入和解析文件前必须选择账簿，支持性文件需要归属到明确账簿。")
    is_enterprise_accountant = _is_enterprise_accountant_context(db, user_id=user_id, ledger_id=ledger_id)
    if is_enterprise_accountant:
        return
    if not project_id:
        return
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=400, detail="审计项目不存在，请先创建或选择项目。")
    if project.type != "audit":
        raise HTTPException(status_code=400, detail="请选择审计类型项目后再实施审计导入。")
    if project.status not in {"active", "draft"}:
        raise HTTPException(status_code=400, detail="审计项目不是可实施状态，请先启动或重新打开项目。")
    link = (
        db.query(ProjectLedger)
        .filter(ProjectLedger.project_id == project_id, ProjectLedger.ledger_id == ledger_id)
        .first()
    )
    if not link:
        raise HTTPException(status_code=400, detail="审计项目尚未绑定当前账簿，请先在账簿管理中完成项目-账簿绑定。")


def _ensure_job_project_ledger_context(db: Session, job: ImportJob, user_id: int | None = None) -> None:
    _ensure_project_ledger_context(
        db,
        project_id=job.project_id,
        ledger_id=job.ledger_id,
        source_type=job.source_type,
        audit_scope_type=job.audit_scope_type,
        user_id=user_id,
    )


def _process_job_background(job_id: int) -> None:
    """后台任务：统一委托 parser-engine 解析最新上传文件。"""
    db = SessionLocal()
    try:
        job = db.get(ImportJob, job_id)
        if job and job.status == "queued":
            _ensure_job_project_ledger_context(db, job)
            source_file = get_latest_source_file(db, job_id)
            if source_file is None:
                mark_missing_source_file(db, job)
                return
            _, summary = parse_source_file_with_unified_engine(db, job, source_file)
            _import_reports[job_id] = summary
    except Exception as exc:
        try:
            job = db.get(ImportJob, job_id)
            source_file = get_latest_source_file(db, job_id)
            if job and source_file:
                mark_parser_engine_failure(db, job, source_file, str(exc))
            elif job:
                job.status = "failed"
                job.error_message = str(exc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("", response_model=ImportJobRead)
def create_job(
    payload: ImportJobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJob:
    """
    创建导入任务

    功能描述：创建新的导入任务，支持指定数据来源类型
    业务逻辑：根据 source_type 区分标准凭证导入与审计序时簿导入

    Args:
        payload: 导入任务创建参数，包含 organization_name, industry, fiscal_year, source_type

    Returns:
        ImportJob: 创建的导入任务
    """
    project_id = payload.project_id
    # 未指定 project_id 且属于审计/需要项目上下文的导入，自动归属到团队“未知项目”
    if project_id is None and _requires_audit_project_context(
        payload.source_type, payload.audit_scope_type, project_id
    ):
        team_id = current_user.team_id
        if team_id is None and payload.ledger_id:
            ledger = db.get(Ledger, payload.ledger_id)
            if ledger:
                team_id = ledger.team_id
        if team_id:
            unknown_project = get_or_create_unknown_project(db, team_id)
            project_id = unknown_project.id

    _ensure_project_ledger_context(
        db,
        project_id=project_id,
        ledger_id=payload.ledger_id,
        source_type=payload.source_type,
        audit_scope_type=payload.audit_scope_type,
        user_id=current_user.id,
    )
    return create_import_job(
        db,
        payload.organization_name,
        payload.industry,
        payload.fiscal_year,
        payload.source_type,
        payload.ledger_id,
        payload.audit_scope_type,
        payload.audit_period_id,
        payload.audit_account_codes,
        project_id,
    )


@router.put("/{job_id}/audit-scope", response_model=ImportJobRead)
def update_audit_scope(
    job_id: int,
    payload: AuditScopeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJob:
    """保存或更新导入任务的审计范围（Step1）。"""
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")

    if payload.audit_scope_type == "by_account" and not payload.audit_account_codes:
        raise HTTPException(status_code=400, detail="按科目审计时必须选择至少一个科目")
    if payload.audit_scope_type == "by_period" and not payload.audit_period_id:
        raise HTTPException(status_code=400, detail="按期间审计时必须选择会计期间")

    _ensure_project_ledger_context(
        db,
        project_id=payload.project_id,
        ledger_id=job.ledger_id,
        source_type=job.source_type,
        audit_scope_type=payload.audit_scope_type,
        user_id=current_user.id,
    )

    job.audit_scope_type = payload.audit_scope_type
    job.audit_period_id = payload.audit_period_id
    job.audit_account_codes = payload.audit_account_codes
    job.project_id = payload.project_id
    db.commit()
    db.refresh(job)
    return job


@router.get("", response_model=list[ImportJobRead])
def list_jobs(ledger_id: int | None = None, db: Session = Depends(get_db)) -> list[ImportJob]:
    query = db.query(ImportJob).order_by(ImportJob.id.desc())
    if ledger_id is not None:
        query = query.filter(ImportJob.ledger_id == ledger_id)
    return query.all()


@router.get("/cleanup-summary")
def import_jobs_cleanup_summary(
    ledger_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.services.audit.import_job_cleanup_service import get_import_job_cleanup_summary

    return get_import_job_cleanup_summary(db, ledger_id=ledger_id)


@router.post("/cleanup")
def import_jobs_cleanup(
    payload: ImportJobCleanupPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.services.audit.import_job_cleanup_service import bulk_purge_import_jobs

    return bulk_purge_import_jobs(
        db,
        ledger_id=payload.ledger_id,
        job_ids=payload.job_ids,
        statuses=payload.statuses,
        keep_job_ids=payload.keep_job_ids,
        stuck_only=payload.stuck_only,
        delete_files=payload.delete_files,
    )


@router.post("/detect-format")
def detect_import_file_format(
    file: UploadFile = File(...),
    charset: str | None = Form(None),
    delimiter: str | None = Form(None),
) -> dict[str, Any]:
    """上传前检测结构化文件编码、分隔符与表头预览（不创建导入任务）。"""
    import os
    import tempfile

    from app.services.doc_parsing.structured_parse_options import parse_options_from_mapping

    suffix = os.path.splitext(file.filename or "")[1].lower() or ".csv"
    parse_options = parse_options_from_mapping({"charset": charset, "delimiter": delimiter})
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(file.file.read())
            temp_path = tmp_file.name
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {exc}") from exc

    try:
        result = detect_structured_file_format(temp_path, parse_options=parse_options)
        result["filename"] = file.filename
        result["parse_options"] = {"charset": charset or "auto", "delimiter": delimiter or "auto"}
        return result
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass


@router.patch("/{job_id}/parse-options", response_model=ImportJobRead)
def update_import_job_parse_options(
    job_id: int,
    payload: ParseOptionsUpdate,
    db: Session = Depends(get_db),
) -> ImportJob:
    from sqlalchemy.orm.attributes import flag_modified

    from app.services.doc_parsing.structured_parse_options import (
        parse_options_from_mapping,
        parse_options_to_mapping,
    )

    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    draft_data = dict(job.draft_data or {})
    draft_data["parse_options"] = parse_options_to_mapping(
        parse_options_from_mapping(payload.model_dump())
    )
    job.draft_data = draft_data
    flag_modified(job, "draft_data")
    db.commit()
    db.refresh(job)
    return job


@router.get("/{job_id}", response_model=ImportJobRead)
def get_job(job_id: int, db: Session = Depends(get_db)) -> ImportJob:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    return job


def _source_file_response(source_file: SourceFile) -> dict[str, Any]:
    parse_feedback = None
    raw_text_preview = None
    if source_file.extracted_text:
        try:
            parsed_text = json.loads(source_file.extracted_text)
            if isinstance(parsed_text, dict):
                parse_feedback = parsed_text.get("parse_feedback")
                raw_text_preview = parsed_text.get("raw_text_preview")
        except json.JSONDecodeError:
            raw_text_preview = source_file.extracted_text[:1000]

    recognized_type = None
    if isinstance(parse_feedback, dict):
        recognized_type = parse_feedback.get("document_type")
    recognized_type = recognized_type or _normalize_evidence_type(source_file) or "unknown"

    return {
        "id": source_file.id,
        "ledger_id": source_file.ledger_id,
        "counterparty_id": source_file.counterparty_id,
        "filename": source_file.filename,
        "file_type": source_file.file_type,
        "upload_status": "uploaded",
        "text_extract_status": source_file.text_extract_status,
        "parse_status": source_file.text_extract_status,
        "recognized_document_type": recognized_type,
        "parse_feedback": parse_feedback,
        "raw_text_preview": raw_text_preview,
        "created_at": source_file.created_at,
    }


@router.post("/{job_id}/files")
def upload_file(
    job_id: int,
    file: UploadFile = File(...),
    document_type_hints: str | None = Form(None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    source_file = attach_file(db, job, file)
    if document_type_hints:
        hints = [hint.strip() for hint in document_type_hints.split(",") if hint.strip()]
        if hints:
            source_file.notes = json.dumps({"document_type_hints": hints}, ensure_ascii=False)
            db.commit()
            db.refresh(source_file)
    return _source_file_response(source_file)


@router.post("/{job_id}/files/{file_id}/parse")
def parse_uploaded_file(job_id: int, file_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    _ensure_job_project_ledger_context(db, job)
    source_file = db.get(SourceFile, file_id)
    if not source_file or source_file.import_job_id != job_id:
        raise HTTPException(status_code=404, detail="上传文件不存在")

    if is_day_book_source_type(job.source_type):
        try:
            report = process_import_job(db, job)
            summary = get_import_summary(report)
            _import_reports[job.id] = summary
            if report.day_book_report is not None:
                _day_book_reports[job.id] = report.day_book_report
            db.refresh(source_file)
            db.refresh(job)
            return {
                **_source_file_response(source_file),
                "job_status": job.status,
                "report": summary,
            }
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"序时簿导入失败: {str(exc)}") from exc

    if job.source_type in AI_EVIDENCE_SOURCE_TYPES:
        try:
            _process_ai_register_file(db, job, source_file)
            db.commit()
            db.refresh(source_file)
            return _source_file_response(source_file)
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"原始资料登记失败: {str(exc)}") from exc

    if _is_source_file(source_file.file_type):
        try:
            _process_source_file(db, job, source_file)
            db.commit()
            db.refresh(source_file)
            return _source_file_response(source_file)
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"原始资料解析失败: {str(exc)}") from exc

    try:
        result_dict, summary = parse_source_file_with_unified_engine(db, job, source_file)
        _import_reports[job.id] = summary
        return {
            **_source_file_response(source_file),
            "parser_engine_result": result_dict,
            "job_status": job.status,
        }
    except Exception as exc:
        mark_parser_engine_failure(db, job, source_file, str(exc))
        raise HTTPException(status_code=500, detail=f"统一解析引擎解析失败: {str(exc)}")


@router.post("/{job_id}/process", response_model=ImportJobRead)
def process_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ImportJob:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    _ensure_job_project_ledger_context(db, job, current_user.id)
    source_file = get_latest_source_file(db, job_id)
    if not source_file:
        raise HTTPException(status_code=400, detail="导入任务尚未上传文件")
    try:
        _, summary = parse_source_file_with_unified_engine(db, job, source_file)
        _import_reports[job.id] = summary
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"统一解析引擎解析失败: {str(exc)}") from exc
    return job


@router.post("/{job_id}/process/sync")
def process_job_sync(job_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """同步处理导入任务：序时簿走专用导入逻辑，其余类型走统一解析引擎。"""
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    _ensure_job_project_ledger_context(db, job)
    resolve_import_job_ledger_id(db, job)
    source_file = get_latest_source_file(db, job_id)
    if not source_file:
        raise HTTPException(status_code=400, detail="导入任务尚未上传文件")
    if is_day_book_source_type(job.source_type) or is_structured_source_type(job.source_type):
        try:
            report = process_import_job(db, job)
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"序时簿导入失败: {str(exc)}") from exc
        summary = get_import_summary(report)
        _import_reports[job.id] = summary
        if report.day_book_report is not None:
            _day_book_reports[job.id] = report.day_book_report
        if report.failed_files == 0 and report.error_message is None:
            job.status = "preview"
            job.entry_count = report.total_entries
        else:
            job.status = "failed"
        if report.error_message:
            job.error_message = report.error_message
        db.commit()
        db.refresh(job)
        return {
            "job": ImportJobRead.model_validate(job).model_dump(mode="json"),
            "report": summary,
        }
    if get_import_output_path(job.source_type) in {"register_ledger", "direct_entries"}:
        try:
            report = process_import_job(db, job)
        except Exception as exc:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"原始资料登记失败: {str(exc)}") from exc
        summary = get_import_summary(report)
        _import_reports[job.id] = summary
        job.status = "completed"
        db.commit()
        db.refresh(job)
        return {
            "job": ImportJobRead.model_validate(job).model_dump(mode="json"),
            "report": summary,
        }
    try:
        result_dict, summary = parse_source_file_with_unified_engine(db, job, source_file)
        _import_reports[job.id] = summary
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"统一解析引擎解析失败: {str(exc)}") from exc
    job.status = "completed"
    db.commit()
    db.refresh(job)
    return {
        "job": ImportJobRead.model_validate(job).model_dump(mode="json"),
        "report": summary,
    }


@router.get("/{job_id}/draft")
def get_job_draft(job_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    获取导入任务的草稿数据

    功能描述：当任务解析失败进入 draft 状态时，返回草稿数据供前端展示
    业务逻辑：
        1. 检查任务是否存在
        2. 返回 draft_data、error_message、status 等字段
        3. 如果任务不是 draft 状态，返回当前状态

    Args:
        job_id: 导入任务 ID

    Returns:
        dict: 包含草稿数据或当前状态
    """
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")

    draft_data = job.draft_data or {}
    if job.status == "processing" and not draft_data:
        if get_latest_source_file(db, job_id) is None:
            mark_missing_source_file(db, job)
            draft_data = job.draft_data or {}
    return {
        "job_id": job.id,
        "status": job.status,
        "error_message": job.error_message,
        "draft_data": job.draft_data,
        "source_type": job.source_type,
        "entry_count": job.entry_count,
        "file_count": job.file_count,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


@router.post("/{job_id}/retry")
def retry_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    重试导入任务

    功能描述：将 draft 状态的任务重置为 created，允许用户重新上传或解析
    业务逻辑：
        1. 检查任务是否存在且为 draft 状态
        2. 重置状态为 created，清空错误信息
        3. 保留 source_files 供用户选择重试

    Args:
        job_id: 导入任务 ID

    Returns:
        dict: 重试后的任务状态
    """
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    _ensure_job_project_ledger_context(db, job)
    if job.status != "draft":
        raise HTTPException(status_code=400, detail="只有 draft 状态的任务可以重试")

    job.status = "created"
    job.error_message = None
    job.draft_data = None
    db.commit()

    return {
        "job_id": job.id,
        "status": job.status,
        "message": "任务已重置，可以重新上传文件",
    }


@router.get("/{job_id}/report")
def get_job_report(job_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """获取导入任务的质量报告和原始文件列表"""
    # 优先从内存获取
    if job_id in _import_reports:
        report = _import_reports[job_id].copy()
    else:
        report = {}

    # 获取任务信息
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")

    # 获取原始文件列表
    source_files = db.query(SourceFile).filter(SourceFile.import_job_id == job_id).all()
    source_file_list = [
        {
            "id": sf.id,
            "filename": sf.filename,
            "file_type": sf.file_type,
            "file_size": getattr(sf, "file_size", None),
            "created_at": sf.created_at.isoformat() if sf.created_at else None,
        }
        for sf in source_files
    ]

    # 获取所有分录并生成报告
    from app.services.shared.data_validator import generate_quality_report
    from app.db.models import AccountingEntry

    entries = db.query(AccountingEntry).filter(AccountingEntry.import_job_id == job_id).all()
    entry_dicts = [
        {
            "voucher_no": e.voucher_no,
            "voucher_date": e.voucher_date,
            "summary": e.summary,
            "account_code": e.account_code,
            "account_name": e.account_name,
            "debit_amount": e.debit_amount,
            "credit_amount": e.credit_amount,
            "counterparty": e.counterparty,
        }
        for e in entries
    ]

    if entry_dicts:
        quality_report = generate_quality_report(entry_dicts)
        response = {
            "job_id": job_id,
            "total_entries": len(entry_dicts),
            "source_files": source_file_list,
            "quality": {
                "overall_score": quality_report.overall_score,
                "valid_entries": quality_report.valid_entries,
                "invalid_entries": quality_report.invalid_entries,
                "common_issues": quality_report.common_issues,
                "recommendations": quality_report.recommendations,
            },
        }
        # 若内存缓存的完整报告包含统一字段 quality_score，同步回填到顶层
        # 保持与 POST /process/sync 返回的 ImportReport 结构一致
        if "quality_score" in report:
            response["quality_score"] = report["quality_score"]
        else:
            response["quality_score"] = quality_report.overall_score
    else:
        response = {
            "job_id": job_id,
            "total_entries": 0,
            "source_files": source_file_list,
            "quality": None,
        }

    for key in ("day_book_report", "output_path", "period_suggestion", "register_summary", "file_summary", "total_files", "success_files", "failed_files"):
        if key in report and key not in response:
            response[key] = report[key]
    return response


@router.get("/{job_id}/day-book-report", response_model=DayBookReportRead)
def get_day_book_report(job_id: int, db: Session = Depends(get_db)) -> DayBookReportRead:
    """
    获取序时簿检测报告

    功能描述：返回审计序时簿导入后的凭证完整性检测报告
    业务逻辑：
        1. 检查任务是否存在且为 audit_day_book 类型
        2. 若已缓存则直接返回，否则重新生成报告
        3. 返回凭证总数、跳号数量、不平衡凭证数量、完整性评分等

    Args:
        job_id: 导入任务 ID

    Returns:
        DayBookReportRead: 序时簿检测报告

    注意事项：
        1. 仅支持 source_type 为 "audit_day_book" 的任务
        2. 报告基于数据库中已保存的分录重新计算
    """
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")

    if not is_day_book_source_type(job.source_type):
        raise HTTPException(status_code=400, detail="该任务不是序时簿导入任务")

    # 优先从内存缓存获取
    if job_id in _day_book_reports:
        report = _day_book_reports[job_id]
        return DayBookReportRead(
            total_vouchers=report.total_vouchers,
            total_entries=report.total_entries,
            skip_count=report.skip_count,
            unbalanced_count=report.unbalanced_count,
            completeness_score=report.completeness_score,
            missing_voucher_nos=report.missing_voucher_nos,
            unbalanced_vouchers=[
                {
                    "voucher_no": v.voucher_no,
                    "voucher_date": v.voucher_date,
                    "debit_total": str(v.debit_total),
                    "credit_total": str(v.credit_total),
                    "difference": str(v.difference),
                    "entry_count": v.entry_count,
                }
                for v in report.unbalanced_vouchers
            ],
        )

    # 重新生成报告（基于数据库中已保存的分录）
    from app.db.models import AccountingEntry
    entries = db.query(AccountingEntry).filter(AccountingEntry.import_job_id == job_id).all()
    if not entries:
        raise HTTPException(status_code=400, detail="该任务尚未导入分录数据")

    # 按 voucher_no 分组
    voucher_groups: dict[str, list[AccountingEntry]] = {}
    for entry in entries:
        voucher_no = entry.voucher_no or f"__no_voucher__:{entry.id}"
        if voucher_no not in voucher_groups:
            voucher_groups[voucher_no] = []
        voucher_groups[voucher_no].append(entry)

    # 逐凭证校验借贷平衡
    unbalanced_vouchers: list[dict[str, Any]] = []
    for voucher_no, voucher_entries in voucher_groups.items():
        if voucher_no.startswith("__no_voucher__"):
            continue
        total_debit = sum(
            (Decimal(str(entry.debit_amount or 0)) for entry in voucher_entries),
            Decimal("0.00")
        )
        total_credit = sum(
            (Decimal(str(entry.credit_amount or 0)) for entry in voucher_entries),
            Decimal("0.00")
        )
        if total_debit.quantize(Decimal("0.00")) != total_credit.quantize(Decimal("0.00")):
            unbalanced_vouchers.append({
                "voucher_no": voucher_no,
                "debit_total": str(total_debit.quantize(Decimal("0.00"))),
                "credit_total": str(total_credit.quantize(Decimal("0.00"))),
                "difference": str(abs(total_debit - total_credit).quantize(Decimal("0.00"))),
                "entry_count": len(voucher_entries),
            })

    # 检测跳号
    all_voucher_nos = [v for v in voucher_groups.keys() if not v.startswith("__no_voucher__")]
    from app.services.audit.audit_day_book_service import _detect_voucher_number_skips
    missing_voucher_nos = _detect_voucher_number_skips(all_voucher_nos)

    total_vouchers = len(voucher_groups)
    skip_count = len(missing_voucher_nos)
    unbalanced_count = len(unbalanced_vouchers)

    # 计算完整性评分
    completeness_score = 100.0
    if total_vouchers > 0:
        skip_penalty = min(skip_count * 2, 20)
        balance_penalty = min(unbalanced_count * 5, 30)
        completeness_score = max(0.0, 100.0 - skip_penalty - balance_penalty)

    return DayBookReportRead(
        total_vouchers=total_vouchers,
        total_entries=len(entries),
        skip_count=skip_count,
        unbalanced_count=unbalanced_count,
        completeness_score=round(completeness_score, 2),
        missing_voucher_nos=missing_voucher_nos,
        unbalanced_vouchers=unbalanced_vouchers,
    )


@router.get("/{job_id}/period-suggestion")
def get_period_suggestion(job_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """根据导入分录凭证日期推荐会计期间（主要用于序时簿导入）。"""
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    return suggest_period_for_job(db, job_id, job.organization_id)


@router.post("/{job_id}/apply-period-mapping")
def apply_period_mapping(
    job_id: int,
    payload: ApplyPeriodMappingPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """为结构化导入任务分配会计期间（序时簿等多期间场景）。"""
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    if not is_day_book_source_type(job.source_type or ""):
        raise HTTPException(status_code=400, detail="仅结构化序时簿导入任务支持期间映射")
    try:
        return apply_import_period_mapping(
            db,
            job,
            period_mapping_mode=payload.period_mapping_mode,
            period_mode=payload.period_mode,
            period_id=payload.period_id,
            period_start_date=payload.period_start_date,
            period_end_date=payload.period_end_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{job_id}/files")
def list_files(job_id: int, db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    files = db.query(SourceFile).filter(SourceFile.import_job_id == job_id).all()
    return [_source_file_response(item) for item in files]


class PreviewEntryPatch(BaseModel):
    summary: str | None = None
    account_code: str | None = None
    account_name: str | None = None
    debit_amount: float | None = None
    credit_amount: float | None = None
    counterparty: str | None = None
    review_status: str | None = None
    tag_updates: list[dict[str, Any]] | None = None
    sync_to_master: bool = False


class DimensionDisplayNamePayload(BaseModel):
    account_code: str
    category_code: str
    tag_value: str
    display_name: str
    source_sub_code: str | None = None
    name_standardized: bool = True
    sync_to_master: bool = False


class StagingLlmResolvePayload(BaseModel):
    staging_ids: list[int] | None = None
    batch_size: int = Field(default=20, ge=1, le=50)
    dry_run: bool = False


class SpotCheckPayload(BaseModel):
    amount_threshold: float


class RandomSamplePayload(BaseModel):
    sample_rate: float | None = Field(default=None, ge=0.01, le=1.0)
    sample_count: int | None = Field(default=None, ge=1)
    seed: int | None = None


class ComplianceReviewPayload(BaseModel):
    mode: Literal["each", "spot", "random", "skip"] = "each"
    voucher_nos: list[str] | None = None
    group_keys: list[str] | None = None
    use_llm: bool = True


class PreviewReviewBatchPayload(BaseModel):
    entry_ids: list[int]
    review_status: str


class PreviewReviewAllPayload(BaseModel):
    review_status: str = "verified"


def _staging_entry_payload(row: StagingAccountingEntry) -> dict[str, Any]:
    original_row = row.original_row or {}
    return {
        "id": row.id,
        "voucher_no": row.voucher_no,
        "voucher_date": row.voucher_date.isoformat() if row.voucher_date else None,
        "summary": row.summary,
        "account_code": row.account_code,
        "account_name": row.account_name,
        "resolved_account_code": row.resolved_account_code,
        "resolved_account_name": row.resolved_account_name,
        "entry_tags_payload": row.entry_tags_payload or [],
        "debit_amount": float(row.debit_amount or 0),
        "credit_amount": float(row.credit_amount or 0),
        "counterparty": row.counterparty,
        "entry_line_no": row.entry_line_no,
        "review_status": row.review_status,
        "source_preparer_name": row.source_preparer_name,
        "cross_reviewed_by_user_id": row.cross_reviewed_by_user_id,
        "cross_reviewed_at": row.cross_reviewed_at.isoformat() if row.cross_reviewed_at else None,
        "compliance_hint": row.compliance_hint,
        "compliance_severity": row.compliance_severity,
        "spot_check_flag": row.spot_check_flag,
        "requires_llm_resolution": bool(original_row.get("_requires_llm_resolution")),
    }


@router.get("/{job_id}/preview-voucher-stats")
def get_preview_voucher_stats(
    job_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    return get_preview_voucher_review_stats(db, job_id)


@router.get("/{job_id}/preview-vouchers")
def get_preview_vouchers(
    job_id: int,
    review_filter: Literal[
        "all",
        "pending",
        "verified",
        "unbalanced",
        "spot_check",
        "compliance_pending",
        "compliance_reviewed",
    ] = "all",
    search: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    items, total, review_stats = list_preview_vouchers(
        db,
        job_id,
        review_filter=review_filter,
        search=search,
        limit=limit,
        offset=offset,
    )
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "review_stats": review_stats,
    }


@router.get("/{job_id}/preview-vouchers/{group_key}/lines")
def get_preview_voucher_lines_route(
    job_id: int,
    group_key: str,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    rows = get_preview_voucher_lines(db, job_id, group_key)
    if rows is None:
        raise HTTPException(status_code=404, detail="凭证不存在")
    from app.services.audit.voucher_signature_service import build_staging_signature_payload

    return {
        "group_key": group_key,
        "signature": build_staging_signature_payload(db, rows),
        "items": [_staging_entry_payload(row) for row in rows],
    }


@router.get("/{job_id}/preview-entries")
def get_preview_entries(
    job_id: int,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    rows, total, review_stats = list_preview_entries(db, job_id, limit=limit, offset=offset)
    return {
        "items": [_staging_entry_payload(row) for row in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
        "review_stats": review_stats,
    }


@router.patch("/{job_id}/preview-entries/{staging_id}")
def patch_preview_entry(
    job_id: int,
    staging_id: int,
    payload: PreviewEntryPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        row, master_sync = update_preview_entry(
            db,
            job_id,
            staging_id,
            payload.model_dump(exclude_unset=True),
            reviewed_by_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not row:
        raise HTTPException(status_code=404, detail="草稿分录不存在")
    return {
        "id": row.id,
        "updated": True,
        "entry": _staging_entry_payload(row),
        "master_sync": master_sync,
    }


@router.post("/{job_id}/dimension-registry/update-display-name")
def update_dimension_display_name(
    job_id: int,
    payload: DimensionDisplayNamePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    try:
        return bulk_update_dimension_display_name(
            db,
            job_id,
            account_code=payload.account_code,
            category_code=payload.category_code,
            tag_value=payload.tag_value,
            display_name=payload.display_name,
            source_sub_code=payload.source_sub_code,
            name_standardized=payload.name_standardized,
            sync_to_master=payload.sync_to_master,
            mapped_by_user_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{job_id}/preview-entries/review-batch")
def batch_review_preview_entries(
    job_id: int,
    payload: PreviewReviewBatchPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    return batch_update_preview_review(
        db,
        job_id,
        payload.entry_ids,
        payload.review_status,
        reviewed_by_user_id=current_user.id,
    )


@router.post("/{job_id}/preview-entries/review-all")
def review_all_preview_entries_route(
    job_id: int,
    payload: PreviewReviewAllPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    return review_all_preview_entries(
        db,
        job_id,
        payload.review_status,
        reviewed_by_user_id=current_user.id,
    )


@router.post("/{job_id}/confirm")
def confirm_import_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    result = confirm_structured_import(db, job, approved_by_user_id=current_user.id)
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error_message or "确认入账失败")
    job.status = "completed"
    job.entry_count = result.entries_created
    db.commit()
    db.refresh(job)
    return {
        "job": ImportJobRead.model_validate(job).model_dump(mode="json"),
        "entries_created": result.entries_created,
    }


@router.post("/{job_id}/cancel")
def cancel_import_job(job_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    cancel_structured_import(db, job)
    db.refresh(job)
    return {"job": ImportJobRead.model_validate(job).model_dump(mode="json"), "cancelled": True}


@router.post("/{job_id}/compliance-spot-check")
def compliance_spot_check(
    job_id: int,
    payload: SpotCheckPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    return apply_compliance_spot_check(db, job_id, Decimal(str(payload.amount_threshold)))


@router.get("/{job_id}/dimension-registry")
def get_dimension_registry(job_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    try:
        return build_staging_dimension_registry(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{job_id}/dimension-pending-queue")
def get_dimension_pending_queue(job_id: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    try:
        return build_dimension_pending_queue(db, job_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{job_id}/staging/llm-pending")
def get_staging_llm_pending(
    job_id: int,
    limit: int = 200,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.services.doc_parsing.staging_llm_tag_resolution_service import StagingLlmTagResolutionService

    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    service = StagingLlmTagResolutionService(db, ledger_id=job.ledger_id)
    rows = service.list_pending_rows(job_id, limit=limit)
    return {
        "job_id": job_id,
        "ledger_id": job.ledger_id,
        "total": len(rows),
        "items": [
            {
                "staging_id": row.id,
                "voucher_no": row.voucher_no,
                "summary": row.summary,
                "account_code": row.resolved_account_code or row.account_code,
                "account_name": row.resolved_account_name or row.account_name,
                "requires_llm_resolution": True,
            }
            for row in rows
        ],
    }


@router.post("/{job_id}/staging/llm-resolve")
def resolve_staging_llm_tags(
    job_id: int,
    payload: StagingLlmResolvePayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.services.doc_parsing.staging_llm_tag_resolution_service import StagingLlmTagResolutionService

    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    service = StagingLlmTagResolutionService(db, ledger_id=job.ledger_id)
    result = service.batch_resolve(
        job_id,
        staging_ids=payload.staging_ids,
        batch_size=payload.batch_size,
        dry_run=payload.dry_run,
    )
    return {
        "task_id": result.task_id,
        "total_rows": result.total_rows,
        "success_count": result.success_count,
        "failed_count": result.failed_count,
        "resolved_rows": result.resolved_rows,
        "processing_time_ms": result.processing_time_ms,
        "error_messages": result.error_messages,
        "suggested_tags": [
            {
                "staging_id": item.entry_id,
                "category_code": item.category_code,
                "tag_value": item.tag_value,
                "display_name": item.display_name,
                "confidence": item.confidence,
                "validation_passed": item.validation_passed,
                "validation_reason": item.validation_reason,
            }
            for item in result.suggested_tags
        ],
    }


@router.post("/{job_id}/compliance-random-sample")
def compliance_random_sample(
    job_id: int,
    payload: RandomSamplePayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    if payload.sample_rate is None and payload.sample_count is None:
        raise HTTPException(status_code=400, detail="请指定 sample_rate 或 sample_count")
    return apply_compliance_random_sample(
        db,
        job_id,
        sample_rate=payload.sample_rate,
        sample_count=payload.sample_count,
        seed=payload.seed,
    )


@router.post("/{job_id}/preview-entries/compliance-review")
def compliance_review(
    job_id: int,
    payload: ComplianceReviewPayload,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    return review_staging_compliance(
        db,
        job_id,
        mode=payload.mode,
        voucher_nos=payload.voucher_nos,
        group_keys=payload.group_keys,
        use_llm=payload.use_llm,
    )


@router.post("/{job_id}/preview-entries/compliance-review/stream")
def compliance_review_stream(
    job_id: int,
    payload: ComplianceReviewPayload,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """SSE 流式合规审查：实时推送本地大模型思索/回复过程。"""
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")

    def event_stream():
        for event in iter_staging_compliance_review(
            db,
            job_id,
            mode=payload.mode,
            voucher_nos=payload.voucher_nos,
            group_keys=payload.group_keys,
            use_llm=payload.use_llm,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
