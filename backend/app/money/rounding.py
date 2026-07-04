# -*- coding: utf-8 -*-
"""
模块功能：统一金额舍入处理
业务场景：为所有财务计算提供一致的舍入方法，防止精度差异
创建日期：2026-07-02
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import TYPE_CHECKING

from app.money.constants import DEFAULT_MONEY_DECIMAL_PLACES, DEFAULT_ROUNDING

if TYPE_CHECKING:
    from app.money.currency import Currency


def round_decimal(value: Decimal, decimal_places: int = DEFAULT_MONEY_DECIMAL_PLACES) -> Decimal:
    """
    功能描述：按指定小数位数量化 Decimal 数值
    业务逻辑：统一采用 ROUND_HALF_UP（四舍五入）
    会计口径：人民币金额通常保留 2 位小数

    Args:
        value: 原始 Decimal 数值
        decimal_places: 保留小数位数，默认 2

    Returns:
        Decimal: 量化后的数值

    示例：
        round_decimal(Decimal("2.345")) -> Decimal("2.35")
        round_decimal(Decimal("2.344")) -> Decimal("2.34")
    """
    quantize_value = Decimal("0." + "0" * decimal_places) if decimal_places > 0 else Decimal("1")
    return value.quantize(quantize_value, rounding=DEFAULT_ROUNDING)


def round_money(value: Decimal, currency: "Currency") -> Decimal:
    """
    功能描述：按币种精度舍入金额
    业务逻辑：根据 currency.minor_unit 确定小数位数

    Args:
        value: Decimal 数值
        currency: Currency 对象

    Returns:
        Decimal: 按币种精度量化后的数值
    """
    return round_decimal(value, currency.minor_unit)


def debit_credit_split(signed_amount: Decimal) -> tuple[Decimal, Decimal]:
    """
    功能描述：将带符号金额拆分为借方/贷方金额
    业务逻辑：正数 -> 借方金额；负数 -> 贷方金额（取绝对值）
    会计口径：符合复式记账中"借正贷负"的约定

    Args:
        signed_amount: 带符号金额

    Returns:
        tuple[Decimal, Decimal]: (debit_amount, credit_amount)
    """
    if signed_amount >= 0:
        return round_decimal(signed_amount), Decimal("0.00")
    return Decimal("0.00"), round_decimal(abs(signed_amount))
