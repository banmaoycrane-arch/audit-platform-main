# -*- coding: utf-8 -*-
"""
模块功能：摘要模板与风险案例匹配服务（存根实现）
业务场景：为分录逻辑校验提供摘要-科目模板匹配和风险案例匹配能力
政策依据：无
输入数据：摘要、借方科目、贷方科目
输出结果：匹配结果列表
创建日期：2026-07-03
更新记录：
    2026-07-03  初始创建存根实现，避免导入错误
"""
from typing import Any

RISK_CASES: list[dict[str, Any]] = []


def match_risk_case(summary: str, debit_account: str, credit_account: str) -> list[dict[str, Any]]:
    """
    根据摘要和借贷科目匹配风险案例。

    Args:
        summary: 摘要文本
        debit_account: 借方科目名称
        credit_account: 贷方科目名称

    Returns:
        list[dict[str, Any]]: 匹配到的风险案例列表，当前存根实现返回空列表
    """
    return []


def match_template(summary: str, debit_account: str, credit_account: str) -> dict[str, Any] | None:
    """
    根据摘要和借贷科目匹配摘要模板。

    Args:
        summary: 摘要文本
        debit_account: 借方科目名称
        credit_account: 贷方科目名称

    Returns:
        dict[str, Any] | None: 匹配到的模板，当前存根实现返回 None
    """
    return None
