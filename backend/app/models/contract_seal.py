# -*- coding: utf-8 -*-
"""
模块功能：印章识别相关 Pydantic 数据模型。
业务场景：定义印章提取请求、响应与列表分页的数据结构，供 API 与前端使用。
政策依据：无。
输入数据：印章识别结果字段。
输出结果：可序列化的请求/响应 Schema。
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建印章 Pydantic 模型
"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class SealTextItemSchema(BaseModel):
    """印章内单个文字项 Schema。"""

    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float


class ContractSealBase(BaseModel):
    """印章基础字段。"""

    contract_id: int
    source_file_id: int | None = None
    page_no: int = 1
    bbox: dict[str, Any]
    seal_image_path: str | None = None
    recognized_text: str | None = None
    text_items: list[SealTextItemSchema] | None = None
    seal_type: str | None = None
    confidence: float = 0.0
    detection_method: str | None = None


class ContractSealCreate(ContractSealBase):
    """创建印章记录请求 Schema。"""

    pass


class ContractSealResponse(ContractSealBase):
    """印章详情响应 Schema。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class ContractSealListResponse(BaseModel):
    """合同下印章列表分页响应 Schema。"""

    total: int
    page: int
    size: int
    items: list[ContractSealResponse]


class ContractSealExtractResponse(BaseModel):
    """印章提取接口响应 Schema。"""

    contract_id: int
    extracted_count: int
    seals: list[ContractSealResponse]


class ContractSealImageAccessResponse(BaseModel):
    """印章子图受控访问响应 Schema（预留）。"""

    seal_id: int
    image_url: str
