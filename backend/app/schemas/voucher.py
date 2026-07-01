# -*- coding: utf-8 -*-
"""
凭证 CRUD 接口 Schema 定义模块。

业务场景：手工录入并管理凭证，支持凭证主表与分录行的创建、读取、更新、删除。
政策依据：符合《企业会计准则》对记账凭证的基本要求。
输入数据：凭证头信息、分录明细行。
输出结果：标准化 Voucher + AccountingEntry 结构，金额保留 2 位小数。

创建日期：2026-07-01
更新记录：
    2026-07-01  初始创建，覆盖 Voucher CRUD 接口输入输出。
"""
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.accounting_entry import AccountingEntryRead


class VoucherLineCreate(BaseModel):
    """
    凭证分录行创建/更新输入。

    业务逻辑：每条分录必须包含科目、摘要、借方或贷方金额。
    会计口径：金额保留 2 位小数，借贷不能同时非零。
    """

    line_no: int = Field(..., ge=1, description="分录行号")
    summary: str = Field(..., min_length=1, description="分录摘要")
    account_code: str = Field(..., min_length=1, description="科目编码")
    account_name: str | None = Field(None, description="科目名称")
    debit_amount: Decimal = Field(
        Decimal("0.00"), ge=Decimal("0.00"), description="借方金额"
    )
    credit_amount: Decimal = Field(
        Decimal("0.00"), ge=Decimal("0.00"), description="贷方金额"
    )
    counterparty: str | None = Field(None, description="对方单位")
    counterparty_id: int | None = Field(None, description="对方单位ID")

    @field_validator("debit_amount", "credit_amount", mode="before")
    @classmethod
    def parse_decimal(cls, value: Any) -> Decimal:
        """将输入金额统一转换为 Decimal 并保留 2 位小数。"""
        if value is None:
            return Decimal("0.00")
        return Decimal(str(value)).quantize(Decimal("0.00"))

    @field_validator("debit_amount")
    @classmethod
    def debit_not_negative(cls, value: Decimal) -> Decimal:
        if value < Decimal("0.00"):
            raise ValueError("借方金额不能为负数")
        return value

    @field_validator("credit_amount")
    @classmethod
    def credit_not_negative(cls, value: Decimal) -> Decimal:
        if value < Decimal("0.00"):
            raise ValueError("贷方金额不能为负数")
        return value

    model_config = {"json_schema_extra": {"examples": [{"line_no": 1, "summary": "办公费", "account_code": "6602", "debit_amount": "1000.00", "credit_amount": "0.00"}]}}


class VoucherCreate(BaseModel):
    """
    凭证创建输入。

    业务逻辑：凭证必须归属账簿、组织、期间，且借贷平衡。
    """

    ledger_id: int = Field(..., description="账簿ID")
    organization_id: int = Field(..., description="组织ID")
    period_id: int = Field(..., description="会计期间ID")
    voucher_type: str = Field(..., min_length=1, max_length=10, description="凭证字")
    voucher_number: str = Field(..., min_length=1, max_length=100, description="凭证号")
    voucher_date: date = Field(..., description="凭证日期")
    summary: str | None = Field(None, description="凭证摘要")
    attachment_count: int = Field(0, ge=0, description="附件数量")
    lines: list[VoucherLineCreate] = Field(..., min_length=2, description="分录明细")

    model_config = {"json_schema_extra": {"examples": [{"ledger_id": 1, "organization_id": 1, "period_id": 3, "voucher_type": "记", "voucher_number": "001", "voucher_date": "2024-01-15", "summary": "支付办公费", "attachment_count": 2, "lines": []}]}}


class VoucherUpdate(BaseModel):
    """
    凭证更新输入。

    业务逻辑：仅草稿状态凭证可整体更新；字段全部可选，传入时替换旧值。
    """

    period_id: int | None = Field(None, description="会计期间ID")
    voucher_type: str | None = Field(None, min_length=1, max_length=10, description="凭证字")
    voucher_number: str | None = Field(None, min_length=1, max_length=100, description="凭证号")
    voucher_date: date | None = Field(None, description="凭证日期")
    summary: str | None = Field(None, description="凭证摘要")
    attachment_count: int | None = Field(None, ge=0, description="附件数量")
    lines: list[VoucherLineCreate] | None = Field(None, min_length=2, description="分录明细")


class VoucherLineResponse(BaseModel):
    """
    凭证分录行响应。

    会计口径：金额以字符串形式返回，保留 2 位小数，避免浮点误差。
    """

    entry_id: int = Field(..., description="分录ID")
    line_no: int = Field(..., description="分录行号")
    summary: str = Field(..., description="摘要")
    account_code: str = Field(..., description="科目编码")
    account_name: str | None = Field(None, description="科目名称")
    debit_amount: str = Field(..., description="借方金额")
    credit_amount: str = Field(..., description="贷方金额")
    counterparty: str | None = Field(None, description="对方单位")
    counterparty_id: int | None = Field(None, description="对方单位ID")

    model_config = {"from_attributes": True}


class VoucherResponse(BaseModel):
    """
    凭证主表响应。
    """

    voucher_id: int = Field(..., description="凭证ID")
    ledger_id: int = Field(..., description="账簿ID")
    organization_id: int = Field(..., description="组织ID")
    period_id: int | None = Field(None, description="会计期间ID")
    voucher_no: str = Field(..., description="凭证号")
    voucher_type: str | None = Field(None, description="凭证字")
    voucher_number: str | None = Field(None, description="凭证号数字段")
    voucher_date: date = Field(..., description="凭证日期")
    summary: str | None = Field(None, description="摘要")
    status: str = Field(..., description="状态")
    total_debit: str = Field(..., description="借方合计")
    total_credit: str = Field(..., description="贷方合计")
    attachment_count: int = Field(0, description="附件数量")
    source_type: str = Field("manual", description="来源类型")
    created_by: int = Field(..., description="制单人ID")
    created_by_name: str | None = Field(None, description="制单人姓名")
    created_at: Any = Field(..., description="创建时间")
    updated_at: Any | None = Field(None, description="更新时间")
    posted_at: Any | None = Field(None, description="过账时间")
    posted_by: int | None = Field(None, description="过账人ID")
    lines: list[VoucherLineResponse] = Field(default_factory=list, description="分录明细")

    model_config = {"from_attributes": True}


class VoucherListItem(BaseModel):
    """
    凭证列表项响应。
    """

    voucher_id: int = Field(..., description="凭证ID")
    voucher_no: str = Field(..., description="凭证号")
    voucher_type: str | None = Field(None, description="凭证字")
    voucher_number: str | None = Field(None, description="凭证号数字段")
    voucher_date: date = Field(..., description="凭证日期")
    summary: str | None = Field(None, description="摘要")
    status: str = Field(..., description="状态")
    total_debit: str = Field(..., description="借方合计")
    total_credit: str = Field(..., description="贷方合计")
    entry_count: int = Field(..., description="分录行数")
    attachment_count: int = Field(0, description="附件数量")
    created_by: int = Field(..., description="制单人ID")
    created_by_name: str | None = Field(None, description="制单人姓名")
    created_at: Any = Field(..., description="创建时间")

    model_config = {"from_attributes": True}


class VoucherListResponse(BaseModel):
    """
    凭证列表分页响应。
    """

    total: int = Field(..., description="总数")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")
    items: list[VoucherListItem] = Field(default_factory=list, description="凭证列表")


class VoucherStatusTransitionRequest(BaseModel):
    """
    凭证状态流转请求。
    """

    target_status: str = Field(..., description="目标状态：verified/posted/cancelled")


class VoucherOperationResponse(BaseModel):
    """
    凭证操作通用响应。
    """

    success: bool = Field(..., description="是否成功")
    data: VoucherResponse | None = Field(None, description="凭证数据")
    message: str = Field(..., description="操作结果信息")
