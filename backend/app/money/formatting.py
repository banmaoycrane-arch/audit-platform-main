# -*- coding: utf-8 -*-
"""
模块功能：统一金额格式化输出
业务场景：为财务报表、凭证、导入预览等提供一致的金额显示格式
创建日期：2026-07-02
"""

from decimal import Decimal

from app.money.amount import Currency, Money
from app.money.constants import CNY
from app.money.parsing import parse_decimal


def format_decimal(
    value: Decimal | str | int | float | None,
    *,
    decimal_places: int = 2,
    symbol: bool = False,
    currency_symbol: str = "¥",
    thousands: bool = True,
    negative_format: str = "minus",
) -> str:
    """
    功能描述：将金额格式化为标准显示字符串
    业务逻辑：支持千分位、货币符号、负数格式
    会计口径：金额统一保留 2 位小数，负数默认显示为 -1,234.56

    Args:
        value: 金额数值
        decimal_places: 小数位数
        symbol: 是否显示货币符号
        currency_symbol: 货币符号，默认 ¥
        thousands: 是否显示千分位
        negative_format: 负数格式，"minus" 表示前导负号，"parens" 表示括号

    Returns:
        str: 格式化后的金额字符串

    示例：
        format_decimal(Decimal("1234.5")) -> "1,234.50"
        format_decimal(Decimal("-1234.5"), symbol=True) -> "-¥1,234.50"
    """
    if value is None:
        value = Decimal("0.00")
    else:
        value = parse_decimal(value, decimal_places=decimal_places)

    # 分离符号和绝对值
    is_negative = value < 0
    abs_value = abs(value)

    # 格式化为指定位数的小数字符串
    format_str = f"{{:,.{decimal_places}f}}" if thousands else f"{{:.{decimal_places}f}}"
    number_str = format_str.format(abs_value)

    prefix = ""
    if symbol:
        prefix = currency_symbol

    if is_negative:
        if negative_format == "parens":
            return f"({prefix}{number_str})"
        return f"-{prefix}{number_str}"

    return f"{prefix}{number_str}"


def format_money(
    money: Money | Decimal | str | int | float,
    *,
    symbol: bool = True,
    thousands: bool = True,
    currency: Currency | None = None,
) -> str:
    """
    功能描述：格式化 Money 对象或金额数值为显示字符串
    业务逻辑：根据币种选择符号和小数位

    Args:
        money: Money 对象或金额数值
        symbol: 是否显示货币符号
        thousands: 是否显示千分位
        currency: 币种对象（当 money 不是 Money 对象时使用）

    Returns:
        str: 格式化后的金额字符串
    """
    if isinstance(money, Money):
        currency = money.currency
        value = money.amount
    else:
        if currency is None:
            currency = CNY
        value = parse_decimal(money, decimal_places=currency.minor_unit)

    return format_decimal(
        value,
        decimal_places=currency.minor_unit,
        symbol=symbol,
        currency_symbol=currency.symbol,
        thousands=thousands,
    )


def format_amount_for_api(value: Decimal | str | int | float | None) -> str:
    """
    功能描述：将金额格式化为 API 传输字符串
    业务逻辑：返回固定 2 位小数的字符串，避免 JSON 中的 float 精度问题

    Args:
        value: 金额数值

    Returns:
        str: "1234.56" 形式的字符串
    """
    if value is None:
        return "0.00"
    decimal_value = parse_decimal(value, decimal_places=2)
    return f"{decimal_value:.2f}"
