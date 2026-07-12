# -*- coding: utf-8 -*-
"""
模块功能：解析修正闭环 API 路由
业务场景：提供人工复核修正记录、规则提取、规则激活的 HTTP 接口，
        支撑文件智能解析的自我学习和稳定性提升闭环。
政策依据：审计追踪要求、AI 不绕过人工复核原则。
输入数据：修正请求、修正记录ID、原始文本。
输出结果：修正记录、规则补丁、应用状态。
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建，实现修正记录的 CRUD 与规则提取/激活接口。
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.parse_correction import ParseCorrection, ParsingRulePatch
from app.schemas.parse_correction import (
    ApplyRulesResponse,
    CreateParseCorrectionRequest,
    ExtractRulesResponse,
    ParseCorrectionListResponse,
    ParseCorrectionResponse,
)
from app.services.doc_parsing.parser_engine.correction_loop_service import (
    apply_dynamic_rules,
    create_correction_record,
    extract_rules_from_correction,
    get_active_rules_by_document_type,
    get_correction_by_id,
    get_pending_corrections,
)

router = APIRouter(prefix="/api/parser-engine/corrections", tags=["parser-corrections"])


def _correction_to_response(correction: ParseCorrection) -> ParseCorrectionResponse:
    """将修正记录对象转换为响应模型。"""
    return ParseCorrectionResponse(
        id=correction.id,
        task_id=correction.task_id,
        document_type=correction.document_type,
        file_name=correction.file_name,
        diff_fields=correction.diff_fields or [],
        correction_reason=correction.correction_reason,
        corrected_by=correction.corrected_by,
        status=correction.status,
        rule_extracted=bool(correction.rule_extracted),
        regression_passed=correction.regression_passed or 0,
        created_at=correction.created_at.isoformat() if correction.created_at else None,
    )


@router.post("", response_model=ParseCorrectionResponse)
def create_correction(
    request: CreateParseCorrectionRequest,
    db: Session = Depends(get_db),
) -> ParseCorrectionResponse:
    """
    创建解析修正记录

    业务含义：人工复核发现解析结果有误时，通过本接口记录正确结果，
    系统后续可从修正中提取规则补丁并自动学习。
    """
    correction = create_correction_record(
        db=db,
        task_id=request.task_id,
        document_type=request.document_type,
        file_name=request.file_name,
        original_result=request.original_result,
        corrected_result=request.corrected_result,
        correction_reason=request.correction_reason,
        corrected_by=request.corrected_by,
        original_text=request.original_text,
    )
    return _correction_to_response(correction)


@router.get("", response_model=ParseCorrectionListResponse)
def list_corrections(
    document_type: str | None = None,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> ParseCorrectionListResponse:
    """
    列出解析修正记录

    - 支持按文档类型、状态过滤
    - 默认返回最近 100 条
    """
    query = db.query(ParseCorrection)
    if document_type:
        query = query.filter(ParseCorrection.document_type == document_type)
    if status:
        query = query.filter(ParseCorrection.status == status)

    total = query.count()
    items = query.order_by(ParseCorrection.created_at.desc()).offset(offset).limit(limit).all()

    return ParseCorrectionListResponse(
        items=[_correction_to_response(item) for item in items],
        total=total,
    )


@router.get("/{correction_id}", response_model=ParseCorrectionResponse)
def get_correction(correction_id: int, db: Session = Depends(get_db)) -> ParseCorrectionResponse:
    """获取单条修正记录详情。"""
    correction = get_correction_by_id(db, correction_id)
    if not correction:
        raise HTTPException(status_code=404, detail="修正记录不存在")
    return _correction_to_response(correction)


@router.post("/{correction_id}/extract-rules", response_model=ExtractRulesResponse)
def extract_rules(
    correction_id: int,
    original_text: str = "",
    db: Session = Depends(get_db),
) -> ExtractRulesResponse:
    """
    从修正记录中提取规则补丁

    业务含义：分析人工修正内容，自动生成正则表达式或字段映射规则补丁。
    提取后规则状态为 draft，需经人工确认或回归验证后激活。
    """
    correction = get_correction_by_id(db, correction_id)
    if not correction:
        raise HTTPException(status_code=404, detail="修正记录不存在")

    patches = extract_rules_from_correction(db, correction_id, original_text)

    return ExtractRulesResponse(
        correction_id=correction_id,
        extracted_patch_count=len(patches),
        patch_names=[p.rule_name for p in patches],
        status=correction.status,
    )


@router.post("/{correction_id}/apply", response_model=ApplyRulesResponse)
def apply_correction_rules(
    correction_id: int,
    db: Session = Depends(get_db),
) -> ApplyRulesResponse:
    """
    激活修正记录关联的规则补丁

    业务含义：人工确认规则正确后，将 draft 状态的规则补丁转为 active，
    后续规则引擎解析时会自动应用这些补丁。
    """
    correction = get_correction_by_id(db, correction_id)
    if not correction:
        raise HTTPException(status_code=404, detail="修正记录不存在")

    patches = (
        db.query(ParsingRulePatch)
        .filter(
            ParsingRulePatch.source_correction_id == correction_id,
            ParsingRulePatch.status == "draft",
        )
        .all()
    )

    applied_count = 0
    for patch in patches:
        patch.status = "active"
        applied_count += 1

    if applied_count > 0:
        correction.status = "applied"
        db.commit()

    return ApplyRulesResponse(
        correction_id=correction_id,
        applied_patch_count=applied_count,
        status=correction.status,
    )


@router.get("/rules/{document_type}")
def list_active_rules(document_type: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """获取指定文档类型的所有生效规则补丁。"""
    rules = get_active_rules_by_document_type(db, document_type)
    return {
        "document_type": document_type,
        "rule_count": len(rules),
        "rules": [
            {
                "id": r.id,
                "rule_name": r.rule_name,
                "rule_type": r.rule_type,
                "target_field": r.target_field,
                "priority": r.priority,
                "confidence_boost": r.confidence_boost,
                "applied_count": r.applied_count,
                "success_rate": r.success_rate,
            }
            for r in rules
        ],
    }


@router.post("/rules/{document_type}/preview")
def preview_rules(
    document_type: str,
    parsed_data: dict[str, Any],
    text: str = "",
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    预览规则补丁对解析结果的影响

    业务含义：在正式激活前，可先预览动态规则应用后的结果，避免误修正。
    """
    applied_data = apply_dynamic_rules(db, document_type, parsed_data.copy(), text)
    changed_fields = [k for k in applied_data if applied_data[k] != parsed_data.get(k)]
    return {
        "document_type": document_type,
        "original_data": parsed_data,
        "applied_data": applied_data,
        "changed_fields": changed_fields,
    }
