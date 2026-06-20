# -*- coding: utf-8 -*-
"""
模块功能：往来重分类规则服务测试
业务场景：验证应收/预收、应付/预付往来余额正负方向的列报建议
政策依据：企业会计准则关于会计科目分类和资产负债列报的基本原则
输入数据：测试用往来科目编码与余额金额
输出结果：重分类服务返回的列报科目、余额方向与语义说明
创建日期：2026-06-19
更新记录：
    2026-06-19  增加 Task 5 往来重分类规则测试
"""
from decimal import Decimal

import pytest

from app.services.reclassification_service import (
    classify_counterparty_balance,
    get_main_account_category,
)


@pytest.mark.parametrize(
    "account_code,balance_amount,expected_direction,expected_code,expected_name",
    [
        ("1122", Decimal("1000.00"), "positive", "1122", "应收账款"),
        ("1122", Decimal("-1000.00"), "negative", "2203", "预收账款"),
        ("2203", Decimal("1000.00"), "positive", "2203", "预收账款"),
        ("2203", Decimal("-1000.00"), "negative", "1122", "应收账款"),
        ("2202", Decimal("1000.00"), "positive", "2202", "应付账款"),
        ("2202", Decimal("-1000.00"), "negative", "1123", "预付账款"),
        ("1123", Decimal("1000.00"), "positive", "1123", "预付账款"),
        ("1123", Decimal("-1000.00"), "negative", "2202", "应付账款"),
    ],
)
def test_classify_counterparty_balance_reclassifies_by_positive_or_negative_balance(
    account_code: str,
    balance_amount: Decimal,
    expected_direction: str,
    expected_code: str,
    expected_name: str,
):
    """
    功能描述：验证往来余额按正负方向给出应收/预收、应付/预付列报建议
    业务逻辑：正数保留本科目正常列报，负数按反方向业务实质重分类
    会计口径：余额金额以本科目正常方向为正数，负数表示反方向余额

    Args:
        account_code: 测试用往来科目编码
        balance_amount: 测试用往来余额金额
        expected_direction: 预期余额方向
        expected_code: 预期列报科目编码
        expected_name: 预期列报科目名称

    Returns:
        None: pytest 断言通过即表示规则符合预期

    注意事项：
        1. 本测试只验证规则服务，不改动现有资产负债表。
    """
    result = classify_counterparty_balance(account_code, balance_amount)

    assert result["original_account_code"] == account_code
    assert result["balance_amount"] == balance_amount
    assert result["balance_direction"] == expected_direction
    assert result["presentation_account_code"] == expected_code
    assert result["presentation_account_name"] == expected_name
    assert result["reason"]


def test_zero_balance_keeps_original_account_without_reclassification():
    """
    功能描述：验证零余额不触发往来重分类
    业务逻辑：余额为零时没有资产或负债列报金额，保持原科目
    会计口径：零余额不形成应收、预收、应付或预付列报差异

    Args:
        无

    Returns:
        None: pytest 断言通过即表示规则符合预期

    注意事项：
        1. 零余额仍返回完整结构，便于前端或后续报表服务统一处理。
    """
    result = classify_counterparty_balance("1122", Decimal("0.00"))

    assert result["balance_direction"] == "zero"
    assert result["presentation_account_code"] == "1122"
    assert result["presentation_account_name"] == "应收账款"
    assert "无需" in result["reason"]


def test_main_account_category_only_describes_standard_account_classification():
    """
    功能描述：验证主科目只返回准则主分类说明
    业务逻辑：主科目负责资产、负债等主分类，不负责判断客户或供应商借贷身份
    会计口径：交易对象语义应通过对方单位和 EntryTag 共同表达

    Args:
        无

    Returns:
        None: pytest 断言通过即表示规则符合预期

    注意事项：
        1. 该测试防止后续将主科目误用为对方单位方向判断工具。
    """
    result = get_main_account_category("1122.01")

    assert result["main_account_code"] == "1122"
    assert result["category"] == "asset"
    assert result["category_name"] == "资产类"
    assert "主分类" in result["role_note"]
    assert "不绑定借方或贷方方向" in result["counterparty_semantic_note"]


def test_counterparty_semantic_note_does_not_change_with_debit_or_credit_direction():
    """
    功能描述：验证对方单位语义说明不随余额正负方向变化
    业务逻辑：同一交易对象可以出现在借方或贷方，借贷方向不改变交易对象本身
    会计口径：具体科目 + EntryTag 才是语义判断依据

    Args:
        无

    Returns:
        None: pytest 断言通过即表示规则符合预期

    注意事项：
        1. 该测试对应 Task 5 的“对方单位不绑定借贷方向”要求。
    """
    positive_result = classify_counterparty_balance("1122", Decimal("1000.00"))
    negative_result = classify_counterparty_balance("1122", Decimal("-1000.00"))

    assert positive_result["counterparty_semantic_note"] == negative_result["counterparty_semantic_note"]
    assert "不绑定借方或贷方方向" in positive_result["counterparty_semantic_note"]
    assert "具体科目和 EntryTag" in positive_result["entry_tag_semantic_note"]
    assert "具体科目和 EntryTag" in negative_result["entry_tag_semantic_note"]
