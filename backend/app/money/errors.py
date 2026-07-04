# -*- coding: utf-8 -*-
"""
模块功能：统一金额处理异常体系
业务场景：为金额解析、校验、计算、转换等操作提供语义化异常
创建日期：2026-07-02
"""

from decimal import Decimal
from typing import Any


class MoneyError(ValueError):
    """金额处理基础异常"""

    def __init__(self, message: str, *, invalid_value: Any = None):
        super().__init__(message)
        self.invalid_value = invalid_value


class MoneyParseError(MoneyError):
    """无法将输入解析为合法金额"""

    def __init__(self, value: Any, message: str | None = None):
        msg = message or f"无法解析为合法金额：{value!r}"
        super().__init__(msg, invalid_value=value)


class MoneyPrecisionError(MoneyError):
    """金额超出允许的小数精度"""

    def __init__(self, value: Any, max_places: int, message: str | None = None):
        msg = message or f"金额 {value!r} 的小数位数超过 {max_places} 位"
        super().__init__(msg, invalid_value=value)


class MoneyRangeError(MoneyError):
    """金额超出最大/最小值限制"""

    def __init__(self, value: Any, min_value: Decimal | None = None, max_value: Decimal | None = None, message: str | None = None):
        msg = message or _build_range_message(value, min_value, max_value)
        super().__init__(msg, invalid_value=value)


def _build_range_message(value: Any, min_value: Decimal | None = None, max_value: Decimal | None = None) -> str:
    if min_value is not None and max_value is not None:
        return f"金额 {value!r} 不在允许范围 [{min_value}, {max_value}] 内"
    if min_value is not None:
        return f"金额 {value!r} 不能小于 {min_value}"
    if max_value is not None:
        return f"金额 {value!r} 不能大于 {max_value}"
    return f"金额 {value!r} 超出允许范围"


class CurrencyNotSupportedError(MoneyError):
    """不支持的币种"""

    def __init__(self, currency_code: str):
        super().__init__(f"不支持的币种：{currency_code}", invalid_value=currency_code)


class ExchangeRateMissingError(MoneyError):
    """缺少币种转换汇率"""

    def __init__(self, from_currency: str, to_currency: str):
        super().__init__(
            f"缺少从 {from_currency} 到 {to_currency} 的汇率",
            invalid_value=(from_currency, to_currency),
        )


class MoneyBalanceError(MoneyError):
    """借贷不平衡"""

    def __init__(self, debit_total: Decimal, credit_total: Decimal, message: str | None = None):
        diff = debit_total - credit_total
        msg = message or f"借贷不平衡：借方 {debit_total}，贷方 {credit_total}，差额 {diff}"
        super().__init__(msg, invalid_value={"debit": debit_total, "credit": credit_total, "diff": diff})
