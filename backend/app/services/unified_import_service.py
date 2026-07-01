# -*- coding: utf-8 -*-
"""
模块功能：统一导入服务
业务场景：为记账和审计两条主线提供统一的导入入口，通过 mode 参数区分处理路径
政策依据：符合《企业会计准则》和审计准则对导入流程的要求
输入数据：导入模式、组织ID、账簿ID、项目ID（审计模式）、文件
输出结果：导入任务、处理报告、期间推荐、检测报告
创建日期：2026-07-02
更新记录：
    2026-07-02  初始创建，实现统一导入入口
"""
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ImportJob, SourceFile

from app.services.import_service import (
    attach_file,
    create_import_job,
    get_import_summary,
    process_import_job,
)
from app.services.import_routing_service import is_day_book_source_type
from app.services.period_detection_service import suggest_period_for_job
from app.services.audit_day_book_service import DayBookReport, process_day_book_import


class UnifiedImportResult:
    """
    统一导入结果

    功能描述：封装导入后的所有结果数据，供前端统一处理
    """
    job_id: int
    job_status: str
    total_entries: int
    success_files: int
    failed_files: int
    day_book_report: DayBookReport | None = None
    period_suggestion: dict | None = None
    error_message: str | None = None


def create_unified_import_job(
    db: Session,
    *,
    organization_id: int,
    ledger_id: int,
    mode: str,
    project_id: int | None = None,
    organization_name: str = "默认企业",
) -> ImportJob:
    """
    创建统一导入任务

    功能描述：根据导入模式创建对应的导入任务
    业务逻辑：
        1. 根据 mode 参数确定 source_type
        2. 记账模式：source_type = ledger_day_book
        3. 审计模式：source_type = audit_day_book（需 project_id）
        4. 创建 ImportJob 记录

    Args:
        db: 数据库会话
        organization_id: 组织ID
        ledger_id: 账簿ID
        mode: 导入模式，可选值：accounting（记账）、audit（审计）
        project_id: 项目ID（审计模式必需）
        organization_name: 组织名称

    Returns:
        ImportJob: 创建的导入任务

    注意事项：
        1. 审计模式必须提供 project_id
        2. source_type 由 mode 自动确定
    """
    if mode == "accounting":
        source_type = "ledger_day_book"
    elif mode == "audit":
        source_type = "audit_day_book"
    else:
        raise ValueError(f"无效的导入模式: {mode}")

    return create_import_job(
        db,
        organization_name=organization_name,
        industry=None,
        fiscal_year=None,
        source_type=source_type,
        ledger_id=ledger_id,
        project_id=project_id,
    )


def upload_and_process_unified_import(
    db: Session,
    *,
    job: ImportJob,
    file: Any,
    file_name: str,
    storage_path: str,
) -> UnifiedImportResult:
    """
    上传并处理统一导入

    功能描述：执行完整的导入流程：上传文件 → 解析 → 校验 → 入库
    业务逻辑：
        1. 保存文件到存储
        2. 创建 SourceFile 记录
        3. 根据 source_type 选择处理路径
        4. 执行导入处理
        5. 生成检测报告（序时簿模式）
        6. 生成期间推荐

    Args:
        db: 数据库会话
        job: 导入任务
        file: 文件对象
        file_name: 文件名
        storage_path: 存储路径

    Returns:
        UnifiedImportResult: 统一导入结果

    注意事项：
        1. 文件必须是 Excel 或 CSV 格式
        2. 序时簿模式会执行跳号检测和借贷平衡校验
        3. 审计模式需要审计项目已绑定账簿
    """
    try:
        source_file = attach_file(
            db,
            import_job_id=job.id,
            file=file,
            filename=file_name,
            storage_path=storage_path,
        )

        db.refresh(job)

        if is_day_book_source_type(job.source_type):
            report = process_import_job(db, job)
            summary = get_import_summary(report)

            day_book_report = report.day_book_report

            period_suggestion = suggest_period_for_job(db, job.id, job.organization_id)
        else:
            report = process_import_job(db, job)
            summary = get_import_summary(report)
            day_book_report = None
            period_suggestion = None

        db.refresh(job)

        return UnifiedImportResult(
            job_id=job.id,
            job_status=job.status,
            total_entries=summary.get("total_entries", 0),
            success_files=summary.get("success_files", 0),
            failed_files=summary.get("failed_files", 0),
            day_book_report=day_book_report,
            period_suggestion=period_suggestion,
        )
    except Exception as exc:
        db.rollback()
        return UnifiedImportResult(
            job_id=job.id,
            job_status="failed",
            total_entries=0,
            success_files=0,
            failed_files=1,
            error_message=str(exc),
        )


def get_unified_import_result(
    db: Session,
    *,
    job_id: int,
) -> UnifiedImportResult:
    """
    获取统一导入结果

    功能描述：根据任务ID获取完整的导入结果
    业务逻辑：
        1. 查询 ImportJob
        2. 获取检测报告（序时簿模式）
        3. 获取期间推荐
        4. 统计导入结果

    Args:
        db: 数据库会话
        job_id: 导入任务ID

    Returns:
        UnifiedImportResult: 统一导入结果

    注意事项：
        1. 任务必须存在
        2. 报告基于已入库的数据重新计算
    """
    job = db.get(ImportJob, job_id)
    if not job:
        raise ValueError("导入任务不存在")

    day_book_report = None
    period_suggestion = None

    if is_day_book_source_type(job.source_type):
        try:
            day_result = process_day_book_import(db, job)
            day_book_report = day_result.report
        except Exception:
            pass

        try:
            period_suggestion = suggest_period_for_job(db, job.id, job.organization_id)
        except Exception:
            pass

    source_files = db.query(SourceFile).filter(
        SourceFile.import_job_id == job_id
    ).all()

    return UnifiedImportResult(
        job_id=job.id,
        job_status=job.status,
        total_entries=job.entry_count,
        success_files=len([f for f in source_files if f.status == "processed"]),
        failed_files=len([f for f in source_files if f.status == "failed"]),
        day_book_report=day_book_report,
        period_suggestion=period_suggestion,
    )