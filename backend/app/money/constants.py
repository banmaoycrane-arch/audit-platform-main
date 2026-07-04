# -*- coding: utf-8 -*-
"""
模块功能：统一金额处理系统的常量定义
业务场景：提供币种、精度、舍入方式等全局常量，作为单一数据源
创建日期：2026-07-02
"""

from decimal import ROUND_HALF_UP

from app.money.currency import Currency


# =============================================================================
# 默认精度和舍入方式
# =============================================================================

# 本位币金额默认保留 2 位小数，与人民币最小单位"分"一致
DEFAULT_MONEY_DECIMAL_PLACES: int = 2

# 统一采用"四舍五入"，符合财务系统常规处理习惯
DEFAULT_ROUNDING = ROUND_HALF_UP

# 金额合法范围：避免前端异常或导入错误导致的天文数字
DEFAULT_MAX_MONEY_VALUE: str = "999999999999.99"
DEFAULT_MIN_MONEY_VALUE: str = "-999999999999.99"


# =============================================================================
# 币种定义
# =============================================================================

CNY: Currency = Currency(
    code="CNY",
    name="人民币",
    symbol="¥",
    minor_unit=2,
)


# 币种注册表（未来扩展多币种时在此注册）
SUPPORTED_CURRENCIES: dict[str, Currency] = {
    CNY.code: CNY,
}


def get_currency(code: str) -> Currency:
    """
    功能描述：根据币种代码获取币种对象
    业务逻辑：从注册表中查询，不存在时抛出异常

    Args:
        code: 币种代码（如 CNY）

    Returns:
        Currency: 币种对象

    Raises:
        CurrencyNotSupportedError: 币种未注册
    """
    from app.money.errors import CurrencyNotSupportedError

    currency = SUPPORTED_CURRENCIES.get(code.upper())
    if not currency:
        raise CurrencyNotSupportedError(code)
    return currency
