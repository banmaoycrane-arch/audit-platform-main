# -*- coding: utf-8 -*-
"""
模块功能：印章识别相关 REST API。
业务场景：提供合同印章提取、列表分页查询、详情查询接口。
政策依据：无。
输入数据：合同 ID、分页参数、用户鉴权信息。
输出结果：印章识别结果摘要、分页列表、单条详情。
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建印章识别 API
"""
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import BACKEND_DIR
from app.core.dependencies import get_current_user
from app.db.models import Contract, ContractSeal, SourceFile
from app.db.session import get_db
from app.models.contract_seal import (
    ContractSealExtractResponse,
    ContractSealListResponse,
    ContractSealResponse,
)
from app.models.user import User
from app.services.doc_parsing.execution_audit_service import create_execution_audit_log
from app.models.project_ledger import ProjectLedger
from app.services.shared.ledger_management_service import user_has_ledger_access
from app.services.shared.project_service import list_projects_by_user
from app.services.basic_data.seal_detection_service import detect_seals
from app.services.basic_data.seal_extraction_service import extract_seal_region
from app.services.basic_data.seal_ocr_service import recognize_seal_text, text_items_to_dict_list

router = APIRouter(prefix="/api/v1", tags=["seals"])


class SealReviewRequest(BaseModel):
    """印章复核请求（预留）。"""

    review_status: str
    review_comment: str | None = None


def _user_can_access_contract(db: Session, user: User, contract: Contract) -> bool:
    """
    功能描述：校验当前用户是否有权访问指定合同。
    业务逻辑：超级管理员直接放行；普通用户需属于合同所属组织，或能访问合同关联的项目/账簿。
    """
    if user.platform_role == "super_admin":
        return True

    # 同一组织下成员可访问
    user_organization_id = getattr(user, "organization_id", None)
    if user_organization_id and contract.organization_id == user_organization_id:
        return True

    # 通过项目授权判断：合同未绑定项目时，检查用户是否有合同所属账簿权限
    user_project_ids = {project.id for project in list_projects_by_user(db, user.id)}
    if user_project_ids and contract.ledger_id is not None:
        contract_project_ids = {
            link.project_id
            for link in db.query(ProjectLedger)
            .filter(ProjectLedger.ledger_id == contract.ledger_id)
            .all()
        }
        if contract_project_ids & user_project_ids:
            return True

    # 兜底：合同有 ledger_id，且用户有账簿权限
    if contract.ledger_id is not None:
        if user_has_ledger_access(db, user.id, contract.ledger_id):
            return True

    return False


def _find_contract_source_file(db: Session, contract: Contract) -> SourceFile | None:
    """
    功能描述：查找合同关联的源文件。
    业务逻辑：优先使用 contract.source_file_id；否则取该组织下最新上传的一张图片作为候选。
    """
    if contract.source_file_id:
        return db.get(SourceFile, contract.source_file_id)

    return (
        db.query(SourceFile)
        .filter(
            SourceFile.organization_id == contract.organization_id,
            SourceFile.file_type.in_(["image", "png", "jpg", "jpeg", "pdf"]),
        )
        .order_by(SourceFile.id.desc())
        .first()
    )


def _seal_type_from_text(recognized_text: str) -> str:
    """
    功能描述：根据识别文字初判印章类型。
    业务逻辑：包含"合同专用章"为合同章；包含"财务"为财务章；包含"法人"为法人章；否则未知。
    """
    if "合同专用章" in recognized_text or "合同章" in recognized_text:
        return "contract_seal"
    if "财务" in recognized_text:
        return "finance_seal"
    if "法人" in recognized_text:
        return "legal_person_seal"
    return "unknown"


def _seal_to_response(seal: ContractSeal) -> ContractSealResponse:
    """功能描述：将 ORM 对象转换为响应 Schema。"""
    return ContractSealResponse.model_validate(seal)


def _resolve_image_path(seal_image_path: str | None) -> Path | None:
    """
    功能描述：将数据库中保存的相对路径解析为绝对路径。
    业务逻辑：绝对路径直接返回；相对路径以 BACKEND_DIR 为根。
    """
    if not seal_image_path:
        return None
    path = Path(seal_image_path)
    if path.is_absolute():
        return path
    return BACKEND_DIR / path


@router.post("/contracts/{contract_id}/seals/extract", response_model=ContractSealExtractResponse)
def extract_contract_seals(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContractSealExtractResponse:
    """
    功能描述：触发指定合同的印章提取流程。
    业务逻辑：校验合同访问权限 → 查找源文件 → 检测印章 → 提取子图 → OCR 识别 → 持久化 → 记录审计日志。
    """
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")

    if not _user_can_access_contract(db, current_user, contract):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该合同")

    source_file = _find_contract_source_file(db, contract)
    if source_file is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="合同未关联可识别源文件",
        )

    image_path = _resolve_image_path(source_file.storage_path)
    if image_path is None or not image_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="合同源文件不存在或路径无效",
        )

    # 检测印章区域
    detected_seals = detect_seals(str(image_path))

    created_seals: list[ContractSeal] = []
    for detection in detected_seals:
        # 提取并预处理印章子图
        seal_sub_image_path = extract_seal_region(
            str(image_path),
            detection.bbox,
            output_dir="app/storage/seals",
        )

        # OCR 识别印章文字，坐标映射回原始页面
        ocr_result = recognize_seal_text(
            str(seal_sub_image_path),
            offset=(detection.bbox[0], detection.bbox[1]),
        )

        recognized_text = ocr_result.recognized_text or ""
        seal_type = _seal_type_from_text(recognized_text)

        seal_record = ContractSeal(
            contract_id=contract_id,
            source_file_id=source_file.id,
            page_no=1,
            bbox={
                "x1": detection.bbox[0],
                "y1": detection.bbox[1],
                "x2": detection.bbox[2],
                "y2": detection.bbox[3],
            },
            seal_image_path=str(seal_sub_image_path),
            recognized_text=recognized_text,
            text_items=text_items_to_dict_list(ocr_result.text_items),
            seal_type=seal_type,
            confidence=detection.confidence,
            detection_method=detection.detection_method,
        )
        db.add(seal_record)
        db.commit()
        db.refresh(seal_record)
        created_seals.append(seal_record)

    # 记录审计日志
    create_execution_audit_log(
        db=db,
        execution_source="manual_ui",
        user=current_user,
        ledger_id=contract.ledger_id,
        tool_name="extract_contract_seals",
        service_name="app.services.seal_services",
        status="success" if created_seals else "success",
        business_object_type="contract_seal",
        business_object_id=str(contract_id),
        input_summary={
            "contract_id": contract_id,
            "source_file_id": source_file.id,
            "detected_count": len(detected_seals),
            "extracted_count": len(created_seals),
        },
    )

    return ContractSealExtractResponse(
        contract_id=contract_id,
        extracted_count=len(created_seals),
        seals=[_seal_to_response(seal) for seal in created_seals],
    )


@router.get("/contracts/{contract_id}/seals", response_model=ContractSealListResponse)
def list_contract_seals(
    contract_id: int,
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContractSealListResponse:
    """
    功能描述：分页查询指定合同下的印章识别结果。
    业务逻辑：校验合同访问权限后返回分页列表。
    """
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="合同不存在")

    if not _user_can_access_contract(db, current_user, contract):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该合同")

    query = db.query(ContractSeal).filter(ContractSeal.contract_id == contract_id)
    total = query.count()
    items = (
        query.order_by(ContractSeal.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    return ContractSealListResponse(
        total=total,
        page=page,
        size=size,
        items=[_seal_to_response(item) for item in items],
    )


@router.get("/seals/{seal_id}", response_model=ContractSealResponse)
def get_seal_detail(
    seal_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ContractSealResponse:
    """
    功能描述：查询单个印章详情。
    业务逻辑：校验当前用户对印章所属合同的访问权限后返回详情。
    """
    seal = db.get(ContractSeal, seal_id)
    if seal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="印章记录不存在")

    contract = db.get(Contract, seal.contract_id)
    if contract is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="印章所属合同不存在")

    if not _user_can_access_contract(db, current_user, contract):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该印章")

    # 查询印章时记录审计日志（只记录访问动作，不影响主流程）
    create_execution_audit_log(
        db=db,
        execution_source="manual_ui",
        user=current_user,
        ledger_id=contract.ledger_id,
        tool_name="get_seal_detail",
        service_name="app.services.seal_services",
        status="success",
        business_object_type="contract_seal",
        business_object_id=str(seal_id),
        input_summary={"contract_id": seal.contract_id, "seal_id": seal_id},
    )

    return _seal_to_response(seal)
