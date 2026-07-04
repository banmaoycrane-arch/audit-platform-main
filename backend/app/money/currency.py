# -*- coding: utf-8 -*-
"""
模块功能：币种定义
业务场景：为金额系统提供不可变的币种对象
创建日期：2026-07-02
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Currency:
    """
    功能描述：币种定义
    业务逻辑：每种币种有唯一代码、名称、符号和小数位数
    会计口径：本系统默认本位币为人民币 CNY，未来可扩展多币种

    Attributes:
        code: 币种代码（如 CNY、USD）
        name: 币种名称
        symbol: 货币符号（如 ¥、$）
        minor_unit: 最小小数位数
    """

    code: str
    name: str
    symbol: str
    minor_unit: int = 2
