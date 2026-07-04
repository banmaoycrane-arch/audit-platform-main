# -*- coding: utf-8 -*-
"""
模块功能：Pydantic 金额字段类型定义
业务场景：在 API Schema 中统一金额字段的序列化和反序列化
创建日期：2026-07-02
"""

from decimal import Decimal
from typing import Annotated, Any

from pydantic import PlainSerializer, PlainValidator

from app.money import parse_decimal, format_amount_for_api


def _validate_money_field(value: Any) -> Decimal:
    """
    功能描述：Pydantic 金额字段校验器
    业务逻辑：将字符串/数字/Decimal 解析为 Decimal 并量化
    """
    return parse_decimal(value, decimal_places=2)


def _serialize_money_field(value: Decimal) -> str:
    """
    功能描述：Pydantic 金额字段序列化器
    业务逻辑：将 Decimal 序列化为字符串返回前端，避免 JSON float 精度问题
    """
    return format_amount_for_api(value)


# 金额字段类型：输入时接受任意金额格式，输出时为字符串
MoneyField = Annotated[
    Decimal,
    PlainValidator(_validate_money_field),
    PlainSerializer(_serialize_money_field, return_type=str),
]


# 可选金额字段
OptionalMoneyField = Annotated[
    Decimal | None,
    PlainValidator(lambda v: None if v is None else _validate_money_field(v)),
    PlainSerializer(lambda v: None if v is None else _serialize_money_field(v), return_type=str | None),
]
