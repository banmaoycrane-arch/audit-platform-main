# -*- coding: utf-8 -*-
"""
模块功能：安全解析任意类型的金额为 Decimal 或 Money
业务场景：处理前端输入、文件导入、API 请求中的金额字段
创建日期：2026-07-02
"""

from decimal import Decimal, InvalidOperation
from typing import Any

from app.money.amount import Currency, Money
from app.money.constants import CNY, DEFAULT_MONEY_DECIMAL_PLACES
from app.money.errors import CurrencyNotSupportedError, MoneyParseError
from app.money.rounding import round_decimal


def _clean_amount_string(value: str) -> str:
    """
    功能描述：清理金额字符串中的货币符号和千分位
    业务逻辑：移除 ¥、$、￥、逗号、空格等非数字字符，但保留负号和小数点

    Args:
        value: 原始金额字符串

    Returns:
        str: 清理后的数字字符串
    """
    cleaned = value.replace("¥", "").replace("￥", "").replace("$", "")
    cleaned = cleaned.replace(",", "").replace(" ", "").replace("　", "")
    cleaned = cleaned.replace("，", "")
    return cleaned


def parse_decimal(
    value: Any,
    *,
    decimal_places: int = DEFAULT_MONEY_DECIMAL_PLACES,
    allow_empty: bool = False,
    empty_default: Decimal = Decimal("0.00"),
) -> Decimal:
    """
    功能描述：将任意类型安全解析为 Decimal
    业务逻辑：支持 Decimal、str、int、float、Money；空值按配置处理
    会计口径：解析后自动量化到指定小数位

    Args:
        value: 待解析的金额值
        decimal_places: 保留小数位数
        allow_empty: 是否允许空值返回默认值
        empty_default: 空值时的默认值

    Returns:
        Decimal: 解析后的 Decimal 数值

    Raises:
        MoneyParseError: 无法解析为合法金额

    示例：
        parse_decimal("1,234.56") -> Decimal("1234.56")
        parse_decimal("¥ 1,234.56") -> Decimal("1234.56")
    """
    if value is None or value == "":
        if allow_empty:
            return empty_default
        raise MoneyParseError(value)

    if isinstance(value, Money):
        return value.amount

    if isinstance(value, Decimal):
        decimal_value = value
    elif isinstance(value, (int, float)):
        try:
            decimal_value = Decimal(str(value))
        except InvalidOperation as exc:
            raise MoneyParseError(value) from exc
    elif isinstance(value, str):
        cleaned = _clean_amount_string(value.strip())
        if cleaned == "":
            if allow_empty:
                return empty_default
            raise MoneyParseError(value)
        try:
            decimal_value = Decimal(cleaned)
        except InvalidOperation as exc:
            raise MoneyParseError(value) from exc
    else:
        raise MoneyParseError(value)

    return round_decimal(decimal_value, decimal_places)


def parse_money(value: Any, currency: Currency | None = None) -> Money:
    """
    功能描述：将任意类型解析为 Money 对象
    业务逻辑：默认使用人民币 CNY

    Args:
        value: 待解析的金额值
        currency: 币种对象，默认 CNY

    Returns:
        Money: 金额对象
    """
    if currency is None:
        currency = CNY

    if isinstance(value, Money):
        if value.currency != currency:
            raise CurrencyNotSupportedError(
                f"币种不一致：{value.currency.code} 与 {currency.code}"
            )
        return value

    decimal_value = parse_decimal(value)
    return Money(decimal_value, currency)
