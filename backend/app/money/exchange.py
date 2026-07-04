# -*- coding: utf-8 -*-
"""
模块功能：币种转换逻辑
业务场景：支持未来多币种场景下的金额转换，当前默认仅支持 CNY
创建日期：2026-07-02
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.money.amount import Currency, Money
from app.money.constants import CNY
from app.money.errors import CurrencyNotSupportedError, ExchangeRateMissingError


class ExchangeRateProvider(Protocol):
    """
    功能描述：汇率提供者接口
    业务逻辑：未来对接外部汇率服务或数据库汇率表时实现此协议
    """

    def get_rate(
        self,
        from_currency: str,
        to_currency: str,
        as_of_date: date | None = None,
    ) -> Decimal:
        """
        功能描述：获取指定币种对的汇率

        Args:
            from_currency: 源币种代码
            to_currency: 目标币种代码
            as_of_date: 汇率日期

        Returns:
            Decimal: 汇率（1单位 from_currency 可兑换多少 to_currency）
        """
        ...


@dataclass
class ConversionResult:
    """币种转换结果"""

    original_money: Money
    converted_money: Money
    rate: Decimal
    as_of_date: date | None


def _default_rate(from_currency: str, to_currency: str, as_of_date: date | None = None) -> Decimal:
    """
    功能描述：默认汇率提供逻辑
    业务逻辑：当前仅支持 CNY 到 CNY 的转换（汇率为1），其他币种需自定义 provider

    Args:
        from_currency: 源币种代码
        to_currency: 目标币种代码
        as_of_date: 汇率日期（当前未使用）

    Returns:
        Decimal: 汇率

    Raises:
        ExchangeRateMissingError: 缺少非 CNY 币种汇率
    """
    from_code = from_currency.upper()
    to_code = to_currency.upper()

    if from_code == to_code:
        return Decimal("1.0000")

    # 当前系统只支持人民币本位币
    if from_code != CNY.code and to_code != CNY.code:
        raise ExchangeRateMissingError(from_currency, to_currency)

    raise ExchangeRateMissingError(from_currency, to_currency)


def convert_money(
    money: Money,
    target_currency: Currency,
    *,
    rate: Decimal | str | int | float | None = None,
    rate_provider: ExchangeRateProvider | None = None,
    as_of_date: date | None = None,
) -> ConversionResult:
    """
    功能描述：将金额转换为目标币种
    业务逻辑：支持显式汇率、自定义汇率提供者或默认汇率提供者

    Args:
        money: 源金额
        target_currency: 目标币种
        rate: 显式汇率（可选）
        rate_provider: 汇率提供者（可选）
        as_of_date: 汇率日期（可选）

    Returns:
        ConversionResult: 转换结果，包含原始金额、转换后金额、汇率和日期

    Raises:
        CurrencyNotSupportedError: 目标币种未注册
        ExchangeRateMissingError: 缺少汇率
    """
    if money.currency == target_currency:
        return ConversionResult(
            original_money=money,
            converted_money=money,
            rate=Decimal("1.0000"),
            as_of_date=as_of_date,
        )

    if rate is not None:
        rate_decimal = Decimal(str(rate))
    elif rate_provider is not None:
        rate_decimal = rate_provider.get_rate(
            money.currency.code, target_currency.code, as_of_date
        )
    else:
        rate_decimal = _default_rate(
            money.currency.code, target_currency.code, as_of_date
        )

    converted_amount = (money.amount * rate_decimal).quantize(
        Decimal("0." + "0" * target_currency.minor_unit),
        rounding="ROUND_HALF_UP",
    )

    return ConversionResult(
        original_money=money,
        converted_money=Money(converted_amount, target_currency),
        rate=rate_decimal,
        as_of_date=as_of_date,
    )
