# -*- coding: utf-8 -*-
"""
模块功能：统一金额输入校验
业务场景：校验用户输入、文件导入、API 请求中的金额字段是否符合业务规则
创建日期：2026-07-02
"""

from decimal import Decimal
from typing import Any

from app.money.amount import Money
from app.money.constants import (
    DEFAULT_MAX_MONEY_VALUE,
    DEFAULT_MIN_MONEY_VALUE,
    DEFAULT_MONEY_DECIMAL_PLACES,
)
from app.money.errors import MoneyPrecisionError, MoneyRangeError
from app.money.parsing import parse_decimal


def validate_decimal_input(
    value: Any,
    *,
    min_value: Decimal | str | int | float | None = None,
    max_value: Decimal | str | int | float | None = None,
    max_decimal_places: int = DEFAULT_MONEY_DECIMAL_PLACES,
    allow_negative: bool = True,
    allow_zero: bool = True,
    field_name: str = "金额",
) -> Decimal:
    """
    功能描述：校验金额输入并返回 Decimal
    业务逻辑：依次执行解析、精度、范围、符号校验
    会计口径：默认金额最小 -999999999999.99，最大 999999999999.99

    Args:
        value: 待校验的金额值
        min_value: 最小值限制
        max_value: 最大值限制
        max_decimal_places: 允许的最大小数位数
        allow_negative: 是否允许负数
        allow_zero: 是否允许为零
        field_name: 字段名称，用于错误信息

    Returns:
        Decimal: 校验通过的 Decimal 数值

    Raises:
        MoneyParseError: 无法解析
        MoneyPrecisionError: 小数位超出限制
        MoneyRangeError: 超出范围
    """
    # 设置默认值
    if min_value is None:
        min_value = Decimal(DEFAULT_MIN_MONEY_VALUE)
    if max_value is None:
        max_value = Decimal(DEFAULT_MAX_MONEY_VALUE)

    min_value = parse_decimal(min_value, decimal_places=max_decimal_places)
    max_value = parse_decimal(max_value, decimal_places=max_decimal_places)

    # 解析
    decimal_value = parse_decimal(value, decimal_places=max_decimal_places)

    # 精度校验：原始值的小数位数不能超过限制
    # 先按 max_decimal_places 量化，再比较量化前后是否相等
    original_decimal = parse_decimal(value, decimal_places=max_decimal_places * 2)
    quantized = parse_decimal(value, decimal_places=max_decimal_places)
    if original_decimal != quantized:
        raise MoneyPrecisionError(
            value, max_decimal_places, f"{field_name} {value} 的小数位数超过 {max_decimal_places} 位"
        )

    # 范围校验
    if decimal_value < min_value or decimal_value > max_value:
        raise MoneyRangeError(
            value,
            min_value=min_value,
            max_value=max_value,
            message=f"{field_name} {value} 不在允许范围 [{min_value}, {max_value}] 内",
        )

    # 符号校验
    if decimal_value < 0 and not allow_negative:
        raise MoneyRangeError(value, message=f"{field_name} 不允许为负数")

    if decimal_value == 0 and not allow_zero:
        raise MoneyRangeError(value, message=f"{field_name} 不允许为零")

    return decimal_value


def validate_money_input(
    value: Any,
    *,
    min_value: Decimal | str | int | float | None = None,
    max_value: Decimal | str | int | float | None = None,
    allow_negative: bool = True,
    allow_zero: bool = True,
) -> Money:
    """
    功能描述：校验金额输入并返回 Money 对象
    业务逻辑：默认使用人民币 CNY

    Args:
        value: 待校验的金额值
        min_value: 最小值限制
        max_value: 最大值限制
        allow_negative: 是否允许负数
        allow_zero: 是否允许为零

    Returns:
        Money: 校验通过的金额对象
    """
    decimal_value = validate_decimal_input(
        value,
        min_value=min_value,
        max_value=max_value,
        allow_negative=allow_negative,
        allow_zero=allow_zero,
    )
    return Money(decimal_value, Money.cny("0").currency)
