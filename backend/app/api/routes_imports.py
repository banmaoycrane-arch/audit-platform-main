import json

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db.models import ImportJob, SourceFile
from app.db.session import SessionLocal, get_db
from app.schemas.import_job import AuditScopeUpdate, DayBookReportRead, ImportJobCreate, ImportJobRead
from app.services.import_service import attach_file, create_import_job, get_import_summary, process_import_job
from app.services.audit_day_book_service import DayBookReport, process_day_book_import
from app.services.entry_generation_service import _normalize_evidence_type
from app.services.import_routing_service import is_day_book_source_type
from app.services.period_detection_service import suggest_period_for_job

router = APIRouter(prefix="/api/import-jobs", tags=["import-jobs"])

# 存储最近导入报告（生产环境应存储到数据库）
_import_reports: dict[int, dict] = {}

# 存储序时簿检测报告（生产环境应存储到数据库）
_day_book_reports: dict[int, DayBookReport] = {}


def _process_job_background(job_id: int) -> None:
    """后台任务：处理导入任务"""
    db = SessionLocal()
    try:
        job = db.get(ImportJob, job_id)
        if job and job.status == "queued":
            job.status = "processing"
            db.commit()
            report = process_import_job(db, job)
            # 保存报告摘要
            _import_reports[job_id] = get_import_summary(report)
    except Exception as exc:
        try:
            job = db.get(ImportJob, job_id)
            if job:
                job.status = "failed"
                job.error_message = str(exc)
                db.commit()
        except:
            pass
    finally:
        db.close()


@router.post("", response_model=ImportJobRead)
def create_job(payload: ImportJobCreate, db: Session = Depends(get_db)) -> ImportJob:
    """
    创建导入任务

    功能描述：创建新的导入任务，支持指定数据来源类型
    业务逻辑：根据 source_type 区分标准凭证导入与审计序时簿导入

    Args:
        payload: 导入任务创建参数，包含 organization_name, industry, fiscal_year, source_type

    Returns:
        ImportJob: 创建的导入任务
    """
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
        payload.project_id,
    )


@router.put("/{job_id}/audit-scope", response_model=ImportJobRead)
def update_audit_scope(
    job_id: int,
    payload: AuditScopeUpdate,
    db: Session = Depends(get_db),
) -> ImportJob:
    """保存或更新导入任务的审计范围（Step1）。"""
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")

    if payload.audit_scope_type == "by_account" and not payload.audit_account_codes:
        raise HTTPException(status_code=400, detail="按科目审计时必须选择至少一个科目")
    if payload.audit_scope_type == "by_period" and not payload.audit_period_id:
        raise HTTPException(status_code=400, detail="按期间审计时必须选择会计期间")

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


@router.get("/{job_id}", response_model=ImportJobRead)
def get_job(job_id: int, db: Session = Depends(get_db)) -> ImportJob:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    return job


def _source_file_response(source_file: SourceFile) -> dict:
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
) -> dict:
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
def parse_uploaded_file(job_id: int, file_id: int, db: Session = Depends(get_db)) -> dict:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    source_file = db.get(SourceFile, file_id)
    if not source_file or source_file.import_job_id != job_id:
        raise HTTPException(status_code=404, detail="上传文件不存在")

    report = process_import_job(db, job)
    _import_reports[job_id] = get_import_summary(report)
    db.refresh(source_file)
    return _source_file_response(source_file)


@router.post("/{job_id}/process", response_model=ImportJobRead)
def process_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ImportJob:
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    
    if job.status in ["processing", "completed"]:
        raise HTTPException(status_code=400, detail=f"任务当前状态为 {job.status}，不能重复处理")
    
    job.status = "queued"
    db.commit()
    db.refresh(job)
    
    background_tasks.add_task(_process_job_background, job_id)
    
    return job


@router.post("/{job_id}/process/sync")
def process_job_sync(job_id: int, db: Session = Depends(get_db)) -> dict:
    """同步处理导入任务（用于调试或小文件），返回导入报告"""
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    report = process_import_job(db, job)
    # 保存报告
    summary = get_import_summary(report)
    _import_reports[job_id] = summary
    if report.day_book_report is not None:
        _day_book_reports[job_id] = report.day_book_report
    return {
        "job": ImportJobRead.model_validate(job).model_dump(mode="json"),
        "report": summary,
    }


@router.get("/{job_id}/draft")
def get_job_draft(job_id: int, db: Session = Depends(get_db)) -> dict:
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
def retry_job(job_id: int, db: Session = Depends(get_db)) -> dict:
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
def get_job_report(job_id: int, db: Session = Depends(get_db)) -> dict:
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
            "file_size": sf.file_size,
            "created_at": sf.created_at.isoformat() if sf.created_at else None,
        }
        for sf in source_files
    ]

    # 获取所有分录并生成报告
    from app.services.data_validator import generate_quality_report
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
        return {
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

    return {
        "job_id": job_id,
        "total_entries": 0,
        "source_files": source_file_list,
        "quality": None,
    }


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
    unbalanced_vouchers: list[dict] = []
    for voucher_no, voucher_entries in voucher_groups.items():
        if voucher_no.startswith("__no_voucher__"):
            continue
        total_debit = sum(
            (entry.debit_amount or 0) for entry in voucher_entries
        )
        total_credit = sum(
            (entry.credit_amount or 0) for entry in voucher_entries
        )
        if round(total_debit, 2) != round(total_credit, 2):
            unbalanced_vouchers.append({
                "voucher_no": voucher_no,
                "debit_total": str(round(total_debit, 2)),
                "credit_total": str(round(total_credit, 2)),
                "difference": str(round(abs(total_debit - total_credit), 2)),
                "entry_count": len(voucher_entries),
            })

    # 检测跳号
    all_voucher_nos = [v for v in voucher_groups.keys() if not v.startswith("__no_voucher__")]
    from app.services.audit_day_book_service import _detect_voucher_number_skips
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
def get_period_suggestion(job_id: int, db: Session = Depends(get_db)) -> dict:
    """根据导入分录凭证日期推荐会计期间（主要用于序时簿导入）。"""
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")
    return suggest_period_for_job(db, job_id, job.organization_id)


@router.get("/{job_id}/files")
def list_files(job_id: int, db: Session = Depends(get_db)) -> list[dict]:
    files = db.query(SourceFile).filter(SourceFile.import_job_id == job_id).all()
    return [_source_file_response(item) for item in files]
