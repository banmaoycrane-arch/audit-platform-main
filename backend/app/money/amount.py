# -*- coding: utf-8 -*-
"""
模块功能：金额领域对象（Currency / Money）
业务场景：为财务系统提供不可变的币种定义和金额计算封装
创建日期：2026-07-02
"""

from decimal import Decimal
from typing import Any, Self

from app.money.currency import Currency
from app.money.errors import CurrencyNotSupportedError, MoneyParseError
from app.money.rounding import round_decimal

__all__ = ["Currency", "Money"]


class Money:
    """
    功能描述：金额领域对象
    业务逻辑：封装 Decimal 金额和币种，提供安全的金额运算
    会计口径：金额使用 Decimal 类型，避免二进制浮点误差；
              所有运算结果按币种小数位自动量化

    Attributes:
        amount: Decimal 金额数值
        currency: Currency 币种对象
    """

    def __init__(self, amount: Decimal | str | int | float, currency: Currency):
        """
        功能描述：构造 Money 对象
        业务逻辑：将任意数值安全转换为 Decimal，并按币种精度量化

        Args:
            amount: 金额数值
            currency: 币种对象

        Raises:
            MoneyParseError: amount 无法解析为合法金额
        """
        self.currency = currency
        self._amount = self._parse_amount(amount)

    @classmethod
    def cny(cls, amount: Decimal | str | int | float) -> Self:
        """构造人民币金额对象"""
        from app.money.constants import CNY

        return cls(amount, CNY)

    def _parse_amount(self, value: Any) -> Decimal:
        """将输入值安全解析并量化为 Decimal"""
        if value is None:
            raise MoneyParseError(None)

        if isinstance(value, Money):
            if value.currency != self.currency:
                raise CurrencyNotSupportedError(
                    f"币种不一致：{value.currency.code} 无法直接转换为 {self.currency.code}"
                )
            return value._amount

        if isinstance(value, Decimal):
            decimal_value = value
        else:
            try:
                decimal_value = Decimal(str(value))
            except Exception as exc:
                raise MoneyParseError(value) from exc

        return round_decimal(decimal_value, self.currency.minor_unit)

    @property
    def amount(self) -> Decimal:
        """返回 Decimal 金额数值"""
        return self._amount

    def add(self, other: "Money") -> "Money":
        """金额相加（币种必须一致）"""
        self._ensure_same_currency(other)
        return Money(self._amount + other._amount, self.currency)

    def subtract(self, other: "Money") -> "Money":
        """金额相减（币种必须一致）"""
        self._ensure_same_currency(other)
        return Money(self._amount - other._amount, self.currency)

    # 常用别名
    sub = subtract

    def multiply(self, factor: Decimal | str | int | float) -> "Money":
        """金额乘以系数"""
        factor_decimal = Decimal(str(factor))
        return Money(self._amount * factor_decimal, self.currency)

    # 常用别名
    mul = multiply

    def divide(self, divisor: Decimal | str | int | float) -> "Money":
        """金额除以除数"""
        divisor_decimal = Decimal(str(divisor))
        if divisor_decimal == 0:
            raise ZeroDivisionError("金额不能除以零")
        return Money(self._amount / divisor_decimal, self.currency)

    # 常用别名
    div = divide

    def abs(self) -> "Money":
        """返回绝对值金额"""
        return Money(self._amount.copy_abs(), self.currency)

    def is_zero(self) -> bool:
        """是否为零"""
        return self._amount == 0

    def is_positive(self) -> bool:
        """是否为正数"""
        return self._amount > 0

    def is_negative(self) -> bool:
        """是否为负数"""
        return self._amount < 0

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.currency == other.currency and self._amount == other._amount

    def __lt__(self, other: "Money") -> bool:
        self._ensure_same_currency(other)
        return self._amount < other._amount

    def __le__(self, other: "Money") -> bool:
        self._ensure_same_currency(other)
        return self._amount <= other._amount

    def __gt__(self, other: "Money") -> bool:
        self._ensure_same_currency(other)
        return self._amount > other._amount

    def __ge__(self, other: "Money") -> bool:
        self._ensure_same_currency(other)
        return self._amount >= other._amount

    def __repr__(self) -> str:
        return f"Money(amount={self._amount}, currency={self.currency.code})"

    def __hash__(self) -> int:
        return hash((self._amount, self.currency.code))

    def _ensure_same_currency(self, other: "Money") -> None:
        """校验两个金额币种一致"""
        if self.currency != other.currency:
            raise CurrencyNotSupportedError(
                f"币种不一致：{self.currency.code} 与 {other.currency.code}"
            )
