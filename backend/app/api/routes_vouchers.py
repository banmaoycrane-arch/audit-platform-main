# -*- coding: utf-8 -*-
"""
凭证独立 CRUD API 路由模块。

业务场景：提供 /api/vouchers RESTful 接口，支持凭证的创建、查询、更新、删除、复核、入账。
政策依据：符合会计准则对记账凭证完整生命周期管理的要求。
输入数据：VoucherCreate / VoucherUpdate / 查询参数 / 状态流转请求。
输出结果：标准化 VoucherResponse 或列表响应。

创建日期：2026-07-01
更新记录：
    2026-07-01  初始创建，实现 Voucher CRUD 及状态流转接口。
"""
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_ledger, get_current_user
from app.db.models import AccountingEntry, Voucher
from app.db.session import get_db
from app.models.user import User
from app.schemas.voucher import (
    VoucherCreate,
    VoucherLineResponse,
    VoucherListItem,
    VoucherListResponse,
    VoucherOperationResponse,
    VoucherResponse,
    VoucherStatusTransitionRequest,
    VoucherUpdate,
)
from app.services.shared import ledger_management_service
from app.services.accounting.voucher_management_service import (
    LedgerAccessError,
    PeriodClosedError,
    VoucherDuplicateError,
    create_voucher_from_request,
    delete_voucher_by_id,
    update_voucher_from_request,
)
from app.services.accounting.voucher_service import (
    VoucherBalanceError,
    VoucherNotFoundError,
    VoucherStateError,
    VoucherStatus,
    VoucherValidationError,
    get_voucher_by_id,
    get_voucher_lines,
    list_vouchers,
    update_voucher_status,
)

router = APIRouter(prefix="/api/vouchers", tags=["vouchers"])


class VoucherQueryParams(BaseModel):
    """凭证列表查询参数。"""
    ledger_id: int = Query(..., description="账簿ID")
    status: str | None = Query(None, description="状态筛选")
    voucher_no: str | None = Query(None, description="凭证号模糊匹配")
    summary: str | None = Query(None, description="摘要模糊匹配")
    start_date: date | None = Query(None, description="凭证日期起始")
    end_date: date | None = Query(None, description="凭证日期截止")
    page: int = Query(1, ge=1, description="页码")
    page_size: int = Query(20, ge=1, le=100, description="每页大小")


class VoucherBatchDeleteRequest(BaseModel):
    """批量删除凭证请求。"""
    voucher_ids: list[int] = Field(..., min_length=1, description="凭证ID列表")


class VoucherBatchDeleteResponse(BaseModel):
    """批量删除凭证响应。"""
    deleted_count: int = Field(..., description="删除数量")


def _format_amount(value: float | Decimal | None) -> str:
    """将金额统一格式化为保留 2 位小数字符串。"""
    if value is None:
        return "0.00"
    return f"{Decimal(str(value)).quantize(Decimal('0.00'))}"


def _format_voucher(voucher: Voucher, db: Session) -> VoucherResponse:
    """将 Voucher ORM 对象转换为响应 Schema。"""
    voucher_type, voucher_number = _split_voucher_no(voucher.voucher_no)
    lines = [
        VoucherLineResponse(
            entry_id=entry.id,
            line_no=entry.entry_line_no,
            summary=entry.summary or "",
            account_code=entry.account_code or "",
            account_name=entry.account_name,
            debit_amount=_format_amount(entry.debit_amount),
            credit_amount=_format_amount(entry.credit_amount),
            counterparty=entry.counterparty,
            counterparty_id=entry.counterparty_id,
        )
        for entry in get_voucher_lines(db, voucher.id)
    ]

    created_by_name = None
    if voucher.created_by:
        user = db.get(User, voucher.created_by)
        if user:
            created_by_name = user.username or user.phone or str(user.id)

    return VoucherResponse(
        voucher_id=voucher.id,
        ledger_id=voucher.ledger_id,
        organization_id=voucher.organization_id,
        period_id=voucher.period_id,
        voucher_no=voucher.voucher_no,
        voucher_type=voucher_type,
        voucher_number=voucher_number,
        voucher_date=voucher.voucher_date,
        summary=voucher.summary,
        status=voucher.status,
        total_debit=_format_amount(voucher.total_debit),
        total_credit=_format_amount(voucher.total_credit),
        attachment_count=voucher.attachment_count or 0,
        source_type=voucher.source_type or "manual",
        created_by=voucher.created_by or 0,
        created_by_name=created_by_name,
        created_at=voucher.created_at,
        updated_at=voucher.updated_at,
        posted_at=voucher.posted_at,
        posted_by=voucher.posted_by,
        lines=lines,
    )


def _format_voucher_list_item(voucher: Voucher, db: Session) -> VoucherListItem:
    """将 Voucher ORM 对象转换为列表项 Schema。"""
    voucher_type, voucher_number = _split_voucher_no(voucher.voucher_no)
    entry_count = db.query(AccountingEntry).filter(
        AccountingEntry.voucher_id == voucher.id
    ).count()

    created_by_name = None
    if voucher.created_by:
        user = db.get(User, voucher.created_by)
        if user:
            created_by_name = user.username or user.phone or str(user.id)

    return VoucherListItem(
        voucher_id=voucher.id,
        voucher_no=voucher.voucher_no,
        voucher_type=voucher_type,
        voucher_number=voucher_number,
        voucher_date=voucher.voucher_date,
        summary=voucher.summary,
        status=voucher.status,
        total_debit=_format_amount(voucher.total_debit),
        total_credit=_format_amount(voucher.total_credit),
        entry_count=entry_count,
        attachment_count=voucher.attachment_count or 0,
        created_by=voucher.created_by or 0,
        created_by_name=created_by_name,
        created_at=voucher.created_at,
    )


def _split_voucher_no(voucher_no: str) -> tuple[str, str]:
    """拆分凭证号为凭证字和凭证号。"""
    if "-" in voucher_no:
        voucher_type, voucher_number = voucher_no.split("-", 1)
        return voucher_type, voucher_number
    return "", voucher_no


@router.post(
    "",
    response_model=VoucherOperationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建凭证",
    description="手工录入凭证，包含凭证头和分录明细，系统自动校验借贷平衡。",
)
def create_voucher_endpoint(data: VoucherCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user), current_ledger_id: int | None = Depends(get_current_ledger)) -> VoucherOperationResponse:
    """
    创建凭证接口。

    业务逻辑：
    1. 校验用户是否有账簿权限。
    2. 校验会计期间是否可录入。
    3. 校验凭证号唯一性。
    4. 校验借贷平衡。
    5. 落库 Voucher 主表和 AccountingEntry 分录行。
    """
    try:
        # 如请求未指定 ledger_id，使用当前账簿
        if not data.ledger_id and current_ledger_id:
            data.ledger_id = current_ledger_id
        voucher = create_voucher_from_request(
            db,
            user=current_user,
            data=data.model_dump(),
        )
        return VoucherOperationResponse(
            success=True,
            data=_format_voucher(voucher, db),
            message="凭证创建成功",
        )
    except (VoucherValidationError, VoucherBalanceError, VoucherDuplicateError, PeriodClosedError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LedgerAccessError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"凭证创建失败：{e}")


@router.get(
    "",
    response_model=VoucherListResponse,
    summary="查询凭证列表",
    description="按账簿、期间、状态、日期等条件查询凭证列表。",
)
def list_vouchers_endpoint(params: VoucherQueryParams = Depends(), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> VoucherListResponse:
    """查询凭证列表接口。"""
    try:
        if not ledger_management_service.user_has_ledger_access(
            db, current_user.id, params.ledger_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"用户无权访问账簿 {params.ledger_id}",
            )

        items, total = list_vouchers(
            db,
            ledger_id=params.ledger_id,
            status=params.status,
            limit=params.page_size,
            offset=(params.page - 1) * params.page_size,
        )

        # 额外过滤
        filtered_items = []
        for voucher in items:
            if params.voucher_no and params.voucher_no not in voucher.voucher_no:
                continue
            if params.summary and (not voucher.summary or params.summary not in voucher.summary):
                continue
            if params.start_date and voucher.voucher_date < params.start_date:
                continue
            if params.end_date and voucher.voucher_date > params.end_date:
                continue
            filtered_items.append(voucher)

        # 重新计算总数（简单实现，后续可优化为 SQL 查询）
        display_total = len(filtered_items)
        formatted_items = [
            _format_voucher_list_item(voucher, db) for voucher in filtered_items
        ]

        return VoucherListResponse(
            total=total,  # 返回原始总数，前端可见筛选后的数量
            page=params.page,
            page_size=params.page_size,
            items=formatted_items,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询凭证列表失败：{e}",
        )


@router.get(
    "/{voucher_id}",
    response_model=VoucherOperationResponse,
    summary="查询凭证详情",
    description="根据凭证ID返回凭证主表和全部分录明细。",
)
def get_voucher_endpoint(voucher_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> VoucherOperationResponse:
    """查询凭证详情接口。"""
    try:
        voucher = get_voucher_by_id(db, voucher_id)
        if not voucher:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"凭证 {voucher_id} 不存在",
            )
        if not ledger_management_service.user_has_ledger_access(
            db, current_user.id, voucher.ledger_id
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"用户无权访问该凭证",
            )
        return VoucherOperationResponse(
            success=True,
            data=_format_voucher(voucher, db),
            message="查询凭证详情成功",
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询凭证详情失败：{e}",
        )


@router.put(
    "/{voucher_id}",
    response_model=VoucherOperationResponse,
    summary="更新凭证",
    description="整体更新凭证头和分录明细，仅草稿状态凭证可编辑。",
)
def update_voucher_endpoint(voucher_id: int, data: VoucherUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> VoucherOperationResponse:
    """更新凭证接口。"""
    try:
        voucher = update_voucher_from_request(
            db,
            user=current_user,
            voucher_id=voucher_id,
            data=data.model_dump(exclude_unset=True),
        )
        return VoucherOperationResponse(
            success=True,
            data=_format_voucher(voucher, db),
            message="凭证更新成功",
        )
    except VoucherNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (VoucherStateError, VoucherValidationError, VoucherBalanceError, VoucherDuplicateError, PeriodClosedError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LedgerAccessError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"凭证更新失败：{e}",
        )


@router.delete(
    "/{voucher_id}",
    response_model=VoucherOperationResponse,
    summary="删除凭证",
    description="删除草稿状态凭证及其全部分录行。",
)
def delete_voucher_endpoint(voucher_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> VoucherOperationResponse:
    """删除凭证接口。"""
    try:
        delete_voucher_by_id(db, user=current_user, voucher_id=voucher_id)
        return VoucherOperationResponse(
            success=True,
            data=None,
            message="凭证删除成功",
        )
    except VoucherNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (VoucherStateError, PeriodClosedError) as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except LedgerAccessError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"凭证删除失败：{e}",
        )


@router.post(
    "/{voucher_id}/verify",
    response_model=VoucherOperationResponse,
    summary="复核凭证",
    description="将草稿状态凭证复核为 verified 状态。",
)
def verify_voucher_endpoint(voucher_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> VoucherOperationResponse:
    """复核凭证接口。"""
    try:
        voucher = get_voucher_by_id(db, voucher_id)
        if not voucher:
            raise VoucherNotFoundError(f"凭证 {voucher_id} 不存在")
        if not ledger_management_service.user_has_ledger_access(
            db, current_user.id, voucher.ledger_id
        ):
            raise LedgerAccessError(f"用户无权访问该凭证")
        if voucher.status != VoucherStatus.DRAFT:
            raise VoucherStateError("只有草稿状态凭证可以复核")

        voucher = update_voucher_status(
            db, voucher_id=voucher_id, status=VoucherStatus.VERIFIED
        )
        return VoucherOperationResponse(
            success=True,
            data=_format_voucher(voucher, db),
            message="凭证复核成功",
        )
    except VoucherNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (VoucherStateError, VoucherValidationError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LedgerAccessError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"凭证复核失败：{e}",
        )


@router.post(
    "/{voucher_id}/post",
    response_model=VoucherOperationResponse,
    summary="入账凭证",
    description="将已复核凭证入账为 posted 状态。",
)
def post_voucher_endpoint(voucher_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> VoucherOperationResponse:
    """入账凭证接口。"""
    try:
        voucher = get_voucher_by_id(db, voucher_id)
        if not voucher:
            raise VoucherNotFoundError(f"凭证 {voucher_id} 不存在")
        if not ledger_management_service.user_has_ledger_access(
            db, current_user.id, voucher.ledger_id
        ):
            raise LedgerAccessError(f"用户无权访问该凭证")
        if voucher.status != VoucherStatus.VERIFIED:
            raise VoucherStateError("只有已复核凭证可以入账")

        voucher = update_voucher_status(
            db,
            voucher_id=voucher_id,
            status=VoucherStatus.POSTED,
            posted_by=current_user.id,
        )
        return VoucherOperationResponse(
            success=True,
            data=_format_voucher(voucher, db),
            message="凭证入账成功",
        )
    except VoucherNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (VoucherStateError, VoucherValidationError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LedgerAccessError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"凭证入账失败：{e}",
        )


@router.post(
    "/{voucher_id}/cancel",
    response_model=VoucherOperationResponse,
    summary="取消凭证",
    description="将凭证状态置为 cancelled，取消后不可再操作。",
)
def cancel_voucher_endpoint(voucher_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> VoucherOperationResponse:
    """取消凭证接口。"""
    try:
        voucher = get_voucher_by_id(db, voucher_id)
        if not voucher:
            raise VoucherNotFoundError(f"凭证 {voucher_id} 不存在")
        if not ledger_management_service.user_has_ledger_access(
            db, current_user.id, voucher.ledger_id
        ):
            raise LedgerAccessError(f"用户无权访问该凭证")
        if voucher.status == VoucherStatus.CANCELLED:
            raise VoucherStateError("凭证已处于取消状态")

        voucher = update_voucher_status(
            db, voucher_id=voucher_id, status=VoucherStatus.CANCELLED
        )
        return VoucherOperationResponse(
            success=True,
            data=_format_voucher(voucher, db),
            message="凭证取消成功",
        )
    except VoucherNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except VoucherStateError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LedgerAccessError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"凭证取消失败：{e}",
        )
