# -*- coding: utf-8 -*-
"""
模块功能：统一导入 API 路由
业务场景：为记账和审计两条主线提供统一的导入入口 API
政策依据：符合《企业会计准则》和审计准则对导入流程的要求
输入数据：导入模式、组织ID、账簿ID、项目ID（审计模式）、文件
输出结果：导入任务、处理报告、期间推荐、检测报告
创建日期：2026-07-02
更新记录：
    2026-07-02  初始创建，实现统一导入 API 端点
"""
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.db.models import ImportJob
from app.services.unified_import_service import (
    create_unified_import_job,
    upload_and_process_unified_import,
    get_unified_import_result,
)
from app.services.import_service import resolve_storage_path
from app.services.import_routing_service import is_day_book_source_type


router = APIRouter(prefix="/api/unified-import", tags=["统一导入"])


@router.post("/jobs")
def create_unified_import_job_api(
    mode: str = Form(...),
    organization_id: int = Form(...),
    ledger_id: int = Form(...),
    project_id: int | None = Form(None),
    organization_name: str = Form("默认企业"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建统一导入任务

    功能描述：根据导入模式创建对应的导入任务
    业务逻辑：
        1. 根据 mode 参数确定 source_type
        2. 记账模式（accounting）：source_type = ledger_day_book
        3. 审计模式（audit）：source_type = audit_day_book（需 project_id）
        4. 创建 ImportJob 记录

    Args:
        mode: 导入模式，可选值：accounting（记账）、audit（审计）
        organization_id: 组织ID
        ledger_id: 账簿ID
        project_id: 项目ID（审计模式必需）
        organization_name: 组织名称

    Returns:
        dict: 创建结果，包含任务ID和状态

    注意事项：
        1. 审计模式必须提供 project_id
        2. 用户必须有账簿访问权限
        3. 审计项目必须已绑定账簿
    """
    if mode not in {"accounting", "audit"}:
        raise HTTPException(status_code=400, detail="无效的导入模式，可选值：accounting、audit")

    if mode == "audit" and not project_id:
        raise HTTPException(status_code=400, detail="审计模式必须提供项目ID")

    try:
        job = create_unified_import_job(
            db,
            organization_id=organization_id,
            ledger_id=ledger_id,
            mode=mode,
            project_id=project_id,
            organization_name=organization_name,
        )
        db.commit()
        db.refresh(job)

        return {
            "success": True,
            "data": {
                "job_id": job.id,
                "source_type": job.source_type,
                "status": job.status,
                "mode": mode,
            },
        }
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建导入任务失败: {str(exc)}") from exc


@router.post("/jobs/{job_id}/upload")
def upload_and_process_unified_import_api(
    job_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
        job_id: 导入任务ID
        file: 上传的文件（Excel/CSV）

    Returns:
        dict: 处理结果，包含任务状态、导入数量、检测报告、期间推荐

    注意事项：
        1. 文件必须是 Excel 或 CSV 格式
        2. 文件大小限制：10MB
        3. 序时簿模式会执行跳号检测和借贷平衡校验
    """
    job = db.get(ImportJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导入任务不存在")

    file_type = file.filename.split(".")[-1].lower() if file.filename else ""
    if file_type not in {"xlsx", "xls", "csv"}:
        raise HTTPException(status_code=400, detail="仅支持 Excel (.xlsx/.xls) 和 CSV 文件")

    storage_path = resolve_storage_path(f"uploads/{job_id}/{file.filename}")

    try:
        file_content = file.file.read()

        result = upload_and_process_unified_import(
            db,
            job=job,
            file=file_content,
            file_name=file.filename,
            storage_path=storage_path,
        )

        db.commit()

        response_data = {
            "success": result.error_message is None,
            "data": {
                "job_id": result.job_id,
                "job_status": result.job_status,
                "total_entries": result.total_entries,
                "success_files": result.success_files,
                "failed_files": result.failed_files,
            },
        }

        if result.day_book_report:
            response_data["data"]["day_book_report"] = {
                "total_vouchers": result.day_book_report.total_vouchers,
                "total_entries": result.day_book_report.total_entries,
                "skip_count": result.day_book_report.skip_count,
                "unbalanced_count": result.day_book_report.unbalanced_count,
                "completeness_score": result.day_book_report.completeness_score,
                "missing_voucher_nos": result.day_book_report.missing_voucher_nos,
                "unbalanced_vouchers": [
                    {
                        "voucher_no": v.voucher_no,
                        "debit_total": str(v.debit_total),
                        "credit_total": str(v.credit_total),
                        "difference": str(v.difference),
                    }
                    for v in result.day_book_report.unbalanced_vouchers
                ],
            }

        if result.period_suggestion:
            response_data["data"]["period_suggestion"] = result.period_suggestion

        if result.error_message:
            response_data["data"]["error_message"] = result.error_message

        return response_data
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"导入处理失败: {str(exc)}") from exc


@router.get("/jobs/{job_id}/result")
def get_unified_import_result_api(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取统一导入结果

    功能描述：根据任务ID获取完整的导入结果
    业务逻辑：
        1. 查询 ImportJob
        2. 获取检测报告（序时簿模式）
        3. 获取期间推荐
        4. 统计导入结果

    Args:
        job_id: 导入任务ID

    Returns:
        dict: 导入结果，包含任务状态、导入数量、检测报告、期间推荐

    注意事项：
        1. 任务必须存在
        2. 报告基于已入库的数据重新计算
    """
    try:
        result = get_unified_import_result(db, job_id=job_id)

        response_data = {
            "success": True,
            "data": {
                "job_id": result.job_id,
                "job_status": result.job_status,
                "total_entries": result.total_entries,
                "success_files": result.success_files,
                "failed_files": result.failed_files,
            },
        }

        if result.day_book_report:
            response_data["data"]["day_book_report"] = {
                "total_vouchers": result.day_book_report.total_vouchers,
                "total_entries": result.day_book_report.total_entries,
                "skip_count": result.day_book_report.skip_count,
                "unbalanced_count": result.day_book_report.unbalanced_count,
                "completeness_score": result.day_book_report.completeness_score,
                "missing_voucher_nos": result.day_book_report.missing_voucher_nos,
                "unbalanced_vouchers": [
                    {
                        "voucher_no": v.voucher_no,
                        "debit_total": str(v.debit_total),
                        "credit_total": str(v.credit_total),
                        "difference": str(v.difference),
                    }
                    for v in result.day_book_report.unbalanced_vouchers
                ],
            }

        if result.period_suggestion:
            response_data["data"]["period_suggestion"] = result.period_suggestion

        return response_data
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"获取导入结果失败: {str(exc)}") from exc