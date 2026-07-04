# -*- coding: utf-8 -*-
"""
测试 app.money 统一金额处理系统
"""

import pytest
from decimal import Decimal

from app.money import (
    CNY,
    Money,
    MoneyBalanceError,
    MoneyParseError,
    MoneyPrecisionError,
    MoneyRangeError,
    format_amount_for_api,
    format_decimal,
    format_money,
    parse_decimal,
    parse_money,
    round_decimal,
    validate_decimal_input,
)
from app.money.exchange import convert_money


class TestParseDecimal:
    """解析测试"""

    def test_parse_string_with_currency_symbol(self):
        assert parse_decimal("¥1,234.56") == Decimal("1234.56")

    def test_parse_string_with_chinese_comma(self):
        assert parse_decimal("1，234.56") == Decimal("1234.56")

    def test_parse_float(self):
        # 注意：float 1.1 实际为 1.1000000000000000888，应通过 str 转换
        result = parse_decimal(1.1)
        assert result == Decimal("1.10")

    def test_parse_invalid(self):
        with pytest.raises(MoneyParseError):
            parse_decimal("abc")


class TestRoundDecimal:
    """舍入测试"""

    def test_round_half_up(self):
        assert round_decimal(Decimal("2.345")) == Decimal("2.35")
        assert round_decimal(Decimal("2.344")) == Decimal("2.34")
        assert round_decimal(Decimal("-2.345")) == Decimal("-2.35")

    def test_avoid_float_error(self):
        # 经典浮点误差：0.1 + 0.2
        result = round_decimal(Decimal("0.1") + Decimal("0.2"))
        assert result == Decimal("0.30")


class TestMoneyOperations:
    """Money 运算测试"""

    def test_add(self):
        a = Money.cny("100.50")
        b = Money.cny("200.25")
        assert a.add(b) == Money.cny("300.75")

    def test_sub(self):
        a = Money.cny("100.00")
        b = Money.cny("30.50")
        assert a.sub(b) == Money.cny("69.50")

    def test_mul(self):
        a = Money.cny("100.00")
        assert a.mul("1.13") == Money.cny("113.00")

    def test_div(self):
        a = Money.cny("100.00")
        assert a.div(3) == Money.cny("33.33")

    def test_div_by_zero(self):
        with pytest.raises(ZeroDivisionError):
            Money.cny("100.00").div(0)

    def test_currency_mismatch(self):
        from app.money.currency import Currency
        from app.money.errors import CurrencyNotSupportedError

        usd = Currency("USD", "美元", "$", 2)
        a = Money.cny("100.00")
        b = Money("100.00", usd)
        with pytest.raises(CurrencyNotSupportedError):
            a.add(b)


class TestFormatting:
    """格式化测试"""

    def test_format_with_symbol_and_thousands(self):
        assert format_decimal(Decimal("1234.5"), symbol=True) == "¥1,234.50"

    def test_format_negative(self):
        assert format_decimal(Decimal("-1234.5"), symbol=True) == "-¥1,234.50"

    def test_format_api(self):
        assert format_amount_for_api(Decimal("1234.5")) == "1234.50"

    def test_format_money(self):
        assert format_money(Money.cny("1234.5")) == "¥1,234.50"


class TestValidation:
    """校验测试"""

    def test_valid_input(self):
        assert validate_decimal_input("100.50") == Decimal("100.50")

    def test_precision_error(self):
        with pytest.raises(MoneyPrecisionError):
            validate_decimal_input("100.555")

    def test_range_error(self):
        with pytest.raises(MoneyRangeError):
            validate_decimal_input("9999999999999.99")

    def test_negative_not_allowed(self):
        with pytest.raises(MoneyRangeError):
            validate_decimal_input("-100", allow_negative=False)

    def test_zero_not_allowed(self):
        with pytest.raises(MoneyRangeError):
            validate_decimal_input("0", allow_zero=False)


class TestExchange:
    """币种转换测试"""

    def test_same_currency(self):
        result = convert_money(Money.cny("100"), CNY)
        assert result.rate == Decimal("1.0000")
        assert result.converted_money == Money.cny("100")

    def test_unsupported_currency(self):
        from app.money.currency import Currency
        from app.money.errors import ExchangeRateMissingError

        usd = Currency("USD", "美元", "$", 2)
        with pytest.raises(ExchangeRateMissingError):
            convert_money(Money.cny("100"), usd)

    def test_explicit_rate(self):
        from app.money.currency import Currency

        usd = Currency("USD", "美元", "$", 2)
        result = convert_money(Money.cny("100"), usd, rate="0.14")
        assert result.converted_money == Money("14.00", usd)
