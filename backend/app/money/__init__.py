# -*- coding: utf-8 -*-
"""
模块功能：统一金额处理系统入口
业务场景：为财务/审计系统提供标准化的金额解析、格式化、校验、舍入和币种转换
政策依据：企业会计准则、项目编码规范
输入数据：任意类型的金额数值或字符串
输出结果：标准化的 Money 对象、格式化字符串或校验结果
创建日期：2026-07-02
更新记录：
    2026-07-02  初始创建，统一金额处理系统
"""

from app.money.amount import Money
from app.money.currency import Currency
from app.money.constants import CNY, DEFAULT_MONEY_DECIMAL_PLACES, DEFAULT_ROUNDING
from app.money.errors import (
    CurrencyNotSupportedError,
    ExchangeRateMissingError,
    MoneyBalanceError,
    MoneyError,
    MoneyParseError,
    MoneyPrecisionError,
    MoneyRangeError,
)
from app.money.exchange import convert_money
from app.money.formatting import format_amount_for_api, format_decimal, format_money
from app.money.parsing import parse_decimal, parse_money
from app.money.rounding import round_decimal, round_money
from app.money.validation import validate_decimal_input, validate_money_input

__all__ = [
    "Currency",
    "Money",
    "CNY",
    "DEFAULT_MONEY_DECIMAL_PLACES",
    "DEFAULT_ROUNDING",
    "MoneyError",
    "MoneyParseError",
    "MoneyPrecisionError",
    "MoneyRangeError",
    "CurrencyNotSupportedError",
    "ExchangeRateMissingError",
    "MoneyBalanceError",
    "parse_decimal",
    "parse_money",
    "format_amount_for_api",
    "format_decimal",
    "format_money",
    "round_decimal",
    "round_money",
    "validate_decimal_input",
    "validate_money_input",
    "convert_money",
]
