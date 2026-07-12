# -*- coding: utf-8 -*-
"""名称规范全称识别测试。"""

import pytest

from app.services.doc_parsing.name_standardization_service import (
    infer_name_standardized,
    name_standardization_queue_message,
)


@pytest.mark.parametrize(
    ("name", "category", "expected"),
    [
        ("山西龙城景辉工业技术科技有限公司", "customer", True),
        ("国网山西省电力公司", "customer", True),
        ("河南锦达建设有限公司", "customer", True),
        ("代县王立矿山机械配件制造加工有限公司", "customer", True),
        ("山西转型综合改革示范区唐槐产业园智青技术服务部", "customer", True),
        ("A客户", "customer", False),
        ("大客户", "customer", False),
        ("招行", "bank_account", False),
        ("农商行", "bank_account", False),
        ("招商银行股份有限公司北京分行", "bank_account", True),
        ("工资", "expense_type", True),
        ("行政部", "department", True),
        ("张悦", "counterparty_object", True),
        ("欧阳明日", "counterparty_object", True),
        ("张胖子", "counterparty_object", False),
        ("李瘦子", "person", False),
        ("张悦", "person", True),
        ("宋", "counterparty_object", False),
        ("宋", "person", False),
        ("大客户", "customer", False),
    ],
)
def test_infer_name_standardized(name: str, category: str, expected: bool):
    account_code = (
        "1002"
        if category in {"account_detail", "bank_account"}
        else "2241"
        if name == "宋" and category == "counterparty_object"
        else "1221"
        if category in {"counterparty_object", "person"}
        else "1122"
    )
    assert (
        infer_name_standardized(
            name,
            category_code=category,
            tag_value=name,
            account_code=account_code,
        )
        is expected
    )


def test_name_standardization_queue_message_for_surname_only():
    msg = name_standardization_queue_message(
        "宋",
        category_code="counterparty_object",
        account_code="2241",
    )
    assert "只有姓氏" in msg
