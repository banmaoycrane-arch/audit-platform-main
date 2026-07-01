# -*- coding: utf-8 -*-
"""
模块功能：解析结果直通凭证草稿的 API 路由
业务场景：用户上传原始资料 → 解析引擎提取字段 → 映射为候选凭证草稿 → 前端预览 → 确认后生成正式草稿
创建日期：2026-07-02
"""

from typing import Any
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.core.dependencies import get_current_user, get_current_ledger
from app.services.parser_engine.parser_engine_dispatcher import ParserEngineDispatcher
from app.services.parser_engine.parse_result import ParseResult
from app.services.parser_voucher_mapper import (
    parse_result_to_voucher_drafts,
    drafts_to_voucher_service_format,
    CandidateVoucherDraft,
)
from app.services.voucher_service import (
    create_vouchers_from_drafts,
    VoucherSourceType,
    VoucherStatus,
)

router = APIRouter(prefix="/api/parser-voucher", tags=["parser-voucher"])


# =============================================================================
# 请求/响应 Schema
# =============================================================================

class CandidateEntryLineResponse(BaseModel):
    """候选分录行响应"""
    account_code: str
    account_name: str
    summary: str
    debit_amount: str
    credit_amount: str
    counterparty: str | None = None


class CandidateVoucherDraftResponse(BaseModel):
    """候选凭证草稿响应"""
    voucher_no: str
    voucher_date: str
    summary: str
    document_type: str
    source_confidence: float
    lines: list[CandidateEntryLineResponse]
    validation_errors: list[str] = []
    raw_extracted_data: dict[str, Any] = {}


class ParseToDraftsResponse(BaseModel):
    """B1: 解析并返回候选凭证草稿列表的响应"""
    success: bool
    document_type: str
    confidence: float
    drafts: list[CandidateVoucherDraftResponse]
    error_message: str | None = None


class ConfirmDraftRequest(BaseModel):
    """B2: 确认生成凭证草稿的请求体"""
    ledger_id: int
    organization_id: int
    drafts: list[dict[str, Any]]  # 用户确认后的草稿列表（可修改科目/金额）


class ConfirmDraftResponse(BaseModel):
    """B2: 确认生成凭证草稿的响应"""
    success: bool
    created_count: int
    voucher_ids: list[int] = []
    error_message: str | None = None


# =============================================================================
# 辅助函数
# =============================================================================

def _extract_parse_result(result: Any) -> ParseResult | None:
    """从解析引擎返回值中提取 ParseResult（兼容多种返回类型）"""
    if isinstance(result, ParseResult):
        return result

    # LLMComparisonResult 类型
    if hasattr(result, "final_result") and result.final_result is not None:
        return result.final_result

    # 双引擎并行解析的 dict 类型
    if isinstance(result, dict):
        final = result.get("final_result")
        if isinstance(final, ParseResult):
            return final
        if isinstance(final, dict):
            # 尝试从 dict 构建一个简化的 ParseResult
            return ParseResult(
                document_type=final.get("document_type", "unknown"),
                data=final.get("data", {}),
                confidence=final.get("confidence", 0.0),
            )

    return None


def _draft_to_response(draft: CandidateVoucherDraft) -> CandidateVoucherDraftResponse:
    """将 CandidateVoucherDraft 转换为 API 响应格式"""
    return CandidateVoucherDraftResponse(
        voucher_no=draft.voucher_no,
        voucher_date=draft.voucher_date,
        summary=draft.summary,
        document_type=draft.document_type,
        source_confidence=draft.source_confidence,
        lines=[
            CandidateEntryLineResponse(
                account_code=line.account_code,
                account_name=line.account_name,
                summary=line.summary,
                debit_amount=str(line.debit_amount),
                credit_amount=str(line.credit_amount),
                counterparty=line.counterparty,
            )
            for line in draft.lines
        ],
        validation_errors=draft.validation_errors,
        raw_extracted_data=draft.raw_extracted_data,
    )


# =============================================================================
# API 端点
# =============================================================================

@router.post("/parse-to-drafts", response_model=ParseToDraftsResponse)
async def parse_to_drafts(
    organization_id: int = Form(..., description="组织ID"),
    file: UploadFile = File(..., description="待解析的文件"),
    sheet_name: str | None = Form(None, description="Excel工作表名称（可选）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    B1: 上传文件并解析为候选凭证草稿列表

    业务流程：
    1. 接收上传的原始资料文件
    2. 调用解析引擎提取结构化字段
    3. 根据文档类型映射为候选凭证草稿
    4. 返回草稿列表供前端预览

    注意：此接口不创建任何数据库记录，仅返回候选草稿
    """
    try:
        # 保存上传文件到临时路径
        import tempfile
        import os
        import shutil

        suffix = os.path.splitext(file.filename or "upload")[1] or ".tmp"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name

        try:
            # 调用解析引擎
            dispatcher = ParserEngineDispatcher(db=db)
            result = await dispatcher.parse(
                file_path=tmp_path,
                user_preselected_type=None,
                sheet_name=sheet_name,
            )
        finally:
            # 清理临时文件
            os.unlink(tmp_path)

        # 提取 ParseResult
        parse_result = _extract_parse_result(result)
        if parse_result is None:
            return ParseToDraftsResponse(
                success=False,
                document_type="unknown",
                confidence=0.0,
                drafts=[],
                error_message="解析引擎未返回有效结果",
            )

        # 映射为候选凭证草稿
        drafts = parse_result_to_voucher_drafts(parse_result)

        if not drafts:
            return ParseToDraftsResponse(
                success=False,
                document_type=str(parse_result.document_type),
                confidence=parse_result.confidence,
                drafts=[],
                error_message=f"文档类型 {parse_result.document_type} 暂不支持自动生成凭证，请手工录入",
            )

        return ParseToDraftsResponse(
            success=True,
            document_type=str(parse_result.document_type),
            confidence=parse_result.confidence,
            drafts=[_draft_to_response(d) for d in drafts],
        )

    except Exception as e:
        return ParseToDraftsResponse(
            success=False,
            document_type="unknown",
            confidence=0.0,
            drafts=[],
            error_message=f"解析失败：{str(e)}",
        )


@router.post("/parse-source-file-to-drafts/{file_id}", response_model=ParseToDraftsResponse)
async def parse_source_file_to_drafts(
    file_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    B1 变体：解析已上传的源文件并返回候选凭证草稿列表

    与 parse-to-drafts 的区别：本接口接收已上传文件的 ID，
    无需重新上传文件，适用于文件已通过导入流程上传的场景。
    """
    from app.db.models import SourceFile

    source_file = db.get(SourceFile, file_id)
    if not source_file:
        raise HTTPException(status_code=404, detail="源文件不存在")

    import os
    if not os.path.exists(source_file.storage_path):
        raise HTTPException(status_code=404, detail="源文件路径不存在")

    try:
        dispatcher = ParserEngineDispatcher(db=db)
        result = await dispatcher.parse(
            file_path=source_file.storage_path,
        )

        parse_result = _extract_parse_result(result)
        if parse_result is None:
            return ParseToDraftsResponse(
                success=False,
                document_type="unknown",
                confidence=0.0,
                drafts=[],
                error_message="解析引擎未返回有效结果",
            )

        drafts = parse_result_to_voucher_drafts(parse_result)

        if not drafts:
            return ParseToDraftsResponse(
                success=False,
                document_type=str(parse_result.document_type),
                confidence=parse_result.confidence,
                drafts=[],
                error_message=f"文档类型 {parse_result.document_type} 暂不支持自动生成凭证",
            )

        return ParseToDraftsResponse(
            success=True,
            document_type=str(parse_result.document_type),
            confidence=parse_result.confidence,
            drafts=[_draft_to_response(d) for d in drafts],
        )

    except Exception as e:
        return ParseToDraftsResponse(
            success=False,
            document_type="unknown",
            confidence=0.0,
            drafts=[],
            error_message=f"解析失败：{str(e)}",
        )


@router.post("/confirm-drafts", response_model=ConfirmDraftResponse)
async def confirm_drafts(
    request: ConfirmDraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_ledger_id: int | None = Depends(get_current_ledger),
):
    """
    B2: 确认候选凭证草稿并生成正式凭证草稿

    业务流程：
    1. 接收用户确认（可能修改过科目/金额）的草稿列表
    2. 调用 voucher_service.create_vouchers_from_drafts 创建草稿凭证
    3. 返回创建的凭证 ID 列表

    注意：
    - 生成的凭证状态为 draft，需人工复核后才可入账
    - source_type 标记为 ai_generated，便于追溯
    - 借贷平衡由 voucher_service 自动校验
    """
    if not request.drafts:
        return ConfirmDraftResponse(
            success=False,
            created_count=0,
            error_message="草稿列表为空",
        )

    ledger_id = request.ledger_id
    if not ledger_id and current_ledger_id:
        ledger_id = current_ledger_id

    if not ledger_id:
        return ConfirmDraftResponse(
            success=False,
            created_count=0,
            error_message="未指定账簿，请先选择账簿",
        )

    try:
        # 将用户确认的草稿转换为 voucher_service 格式
        draft_dicts = []
        for draft in request.drafts:
            for line in draft.get("lines", []):
                draft_dicts.append({
                    "voucher_no": draft.get("voucher_no", ""),
                    "voucher_date": draft.get("voucher_date", ""),
                    "summary": draft.get("summary", ""),
                    "account_code": line.get("account_code", ""),
                    "account_name": line.get("account_name", ""),
                    "debit_amount": str(line.get("debit_amount", "0")),
                    "credit_amount": str(line.get("credit_amount", "0")),
                    "counterparty": line.get("counterparty"),
                })

        # 调用凭证服务创建草稿
        vouchers = create_vouchers_from_drafts(
            db,
            ledger_id=ledger_id,
            organization_id=request.organization_id,
            drafts=draft_dicts,
            source_type=VoucherSourceType.AI_GENERATED,
            created_by=current_user.id,
            status=VoucherStatus.DRAFT,
        )

        return ConfirmDraftResponse(
            success=True,
            created_count=len(vouchers),
            voucher_ids=[v.id for v in vouchers],
        )

    except ValueError as e:
        return ConfirmDraftResponse(
            success=False,
            created_count=0,
            error_message=f"借贷平衡校验失败：{str(e)}",
        )
    except Exception as e:
        return ConfirmDraftResponse(
            success=False,
            created_count=0,
            error_message=f"创建凭证草稿失败：{str(e)}",
        )
