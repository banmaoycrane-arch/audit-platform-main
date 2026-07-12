# -*- coding: utf-8 -*-
"""
科目与标签解析服务单元测试。

测试范围：
    - 一级科目保留
    - 强制二级/三级科目保留完整层级
    - 辅助核算维度转 Tag
    - 往来单位名称识别
    - 摘要补充识别辅助核算维度
"""

import pytest

from app.services.doc_parsing.account_tag_resolution_service import (
    resolve_account_for_import,
)


def test_resolve_first_level_account():
    """一级科目应直接保留，不生成 Tag。"""
    result = resolve_account_for_import("1002", "银行存款", "收到货款")

    assert result.account_code == "1002"
    assert result.account_name == "银行存款"
    assert result.suggested_tags == []
    assert result.counterparty_name is None
    assert result.requires_llm_resolution is False


def test_resolve_undotted_bank_sub_account():
    """6 位无点号编码应扁平化为一级科目，名称下级段转 Tag。"""
    result = resolve_account_for_import("100202", "银行存款_农商行", "现金存入")

    assert result.account_code == "1002"
    assert result.account_name == "银行存款"
    assert len(result.suggested_tags) == 1
    assert result.suggested_tags[0]["category_code"] == "bank_account"
    assert result.suggested_tags[0]["tag_value"] == "农商行"
    assert result.suggested_tags[0]["source_sub_code"] == "02"
    assert result.source_sub_code == "02"


def test_resolve_undotted_mandatory_vat_code():
    """8 位无点号强制层级编码应保留完整层级。"""
    result = resolve_account_for_import("22210101", "应交税费-应交增值税-进项税额", "采购")

    assert result.account_code == "2221.01.01"
    assert "进项税额" in result.account_name
    assert result.suggested_tags == []


def test_resolve_mandatory_vat_input_tax():
    """应交增值税进项税额应保留完整层级。"""
    result = resolve_account_for_import(
        "2221.01.01", "应交税费-应交增值税-进项税额", "采购原材料"
    )

    assert result.account_code == "2221.01.01"
    assert result.account_name == "应交税费-应交增值税-进项税额"
    assert result.suggested_tags == []
    assert result.requires_llm_resolution is False


def test_resolve_mandatory_salary_payable():
    """应付职工薪酬工资应保留完整层级。"""
    result = resolve_account_for_import(
        "2211.01.01", "应付职工薪酬-工资", "计提工资"
    )

    assert result.account_code == "2211.01.01"
    assert result.account_name == "应付职工薪酬-工资"
    assert result.suggested_tags == []


def test_resolve_fixed_asset_composite_name_splits_to_tags():
    """固定资产/累计折旧/在建工程/短期借款：一级科目保留，下级名称段转 Tag。"""
    fa = resolve_account_for_import("1601", "固定资产_房屋建筑物—堆场及封闭棚", "购置")
    assert fa.account_code == "1601"
    assert fa.account_name == "固定资产"
    assert len(fa.suggested_tags) == 2
    assert fa.suggested_tags[0]["category_code"] == "fixed_asset_class"
    assert fa.suggested_tags[0]["tag_value"] == "房屋建筑物"
    assert fa.suggested_tags[1]["category_code"] == "fixed_asset_item"
    assert fa.suggested_tags[1]["tag_value"] == "堆场及封闭棚"

    dep = resolve_account_for_import("1602", "累计折旧_厂房折旧_堆场及封闭棚", "计提折旧")
    assert dep.account_code == "1602"
    assert [t["tag_value"] for t in dep.suggested_tags] == ["厂房折旧", "堆场及封闭棚"]

    cip = resolve_account_for_import("1604", "在建工程_选别车间（磁选/反浮选）", "工程支出")
    assert cip.account_code == "1604"
    assert cip.suggested_tags[0]["category_code"] == "cip_category"
    assert cip.suggested_tags[0]["tag_value"] == "选别车间（磁选/反浮选）"

    loan = resolve_account_for_import("2001", "短期借款_其他个人_李兰旺", "借款")
    assert loan.account_code == "2001"
    assert loan.suggested_tags[0]["tag_value"] == "其他个人"
    assert loan.suggested_tags[1]["category_code"] == "counterparty"
    assert loan.suggested_tags[1]["tag_value"] == "李兰旺"


def test_resolve_equity_sub_accounts_keep_hierarchy():
    """所有者权益二级明细（盈余公积/资本公积/实收资本）保留科目编码，不转 Tag。"""
    statutory = resolve_account_for_import("4101.01", "盈余公积-法定盈余公积", "计提盈余公积")
    assert statutory.account_code == "4101.01"
    assert "法定盈余公积" in statutory.account_name
    assert statutory.suggested_tags == []

    discretionary = resolve_account_for_import("410102", "盈余公积-任意盈余公积", "计提")
    assert discretionary.account_code == "4101.02"
    assert discretionary.suggested_tags == []

    capital_premium = resolve_account_for_import("4002.01", "资本公积-资本溢价", "增资溢价")
    assert capital_premium.account_code == "4002.01"
    assert capital_premium.suggested_tags == []

    paid_in = resolve_account_for_import("4001.01", "实收资本-甲公司", "收到投资")
    assert paid_in.account_code == "4001.01"
    assert paid_in.suggested_tags == []


def test_resolve_receivable_with_full_customer_name():
    """完整法人名称的客户不应标记为简称。"""
    full_name = "山西龙城景辉工业技术科技有限公司"
    result = resolve_account_for_import("1122.01", f"应收账款-{full_name}", "销售商品")

    assert result.suggested_tags[0]["category_code"] == "customer"
    assert result.suggested_tags[0]["tag_value"] == full_name
    assert result.suggested_tags[0]["name_standardized"] is True


def test_resolve_receivable_with_customer():
    """应收账款下级段应转为客户 Tag 并识别往来单位。"""
    result = resolve_account_for_import(
        "1122.01", "应收账款-A客户", "销售商品"
    )

    assert result.account_code == "1122"
    assert result.account_name == "应收账款"
    assert len(result.suggested_tags) == 1
    assert result.suggested_tags[0]["category_code"] == "customer"
    assert result.suggested_tags[0]["tag_value"] == "A客户"
    assert result.counterparty_name == "A客户"


def test_resolve_payable_with_supplier():
    """应付账款下级段应转为供应商 Tag。"""
    result = resolve_account_for_import(
        "2202.03", "应付账款-北京供应商", "采购办公用品"
    )

    assert result.account_code == "2202"
    assert result.account_name == "应付账款"
    assert result.suggested_tags[0]["category_code"] == "supplier"
    assert result.suggested_tags[0]["tag_value"] == "北京供应商"
    assert result.counterparty_name == "北京供应商"


def test_resolve_expense_with_type_and_department():
    """管理费用下级段应转为费用类型和部门 Tag。"""
    result = resolve_account_for_import(
        "6602.01", "管理费用-工资-行政部", "计提工资"
    )

    assert result.account_code == "6602"
    assert result.account_name == "管理费用"
    assert result.suggested_tags[0]["category_code"] == "expense_type"
    assert result.suggested_tags[0]["tag_value"] == "工资"
    assert result.suggested_tags[1]["category_code"] == "department"
    assert result.suggested_tags[1]["tag_value"] == "行政部"


def test_resolve_revenue_with_product():
    """主营业务收入下级段应转为产品 Tag。"""
    result = resolve_account_for_import(
        "6001.02", "主营业务收入-产品B", "销售产品B"
    )

    assert result.account_code == "6001"
    assert result.account_name == "主营业务收入"
    assert result.suggested_tags[0]["category_code"] == "product"
    assert result.suggested_tags[0]["tag_value"] == "产品B"


def test_resolve_infer_from_account_name_only():
    """仅提供科目名称时也能推断一级科目和辅助核算维度。"""
    result = resolve_account_for_import(
        "", "1122.05 应收账款-大客户", "销售回款"
    )

    assert result.account_code == "1122"
    assert result.account_name == "应收账款"
    assert result.suggested_tags[0]["category_code"] == "customer"
    assert result.suggested_tags[0]["tag_value"] == "大客户"


def test_resolve_summary_auxiliary_tags():
    """当科目无法识别辅助核算维度时，尝试从摘要补充。"""
    result = resolve_account_for_import(
        "6602", "管理费用", "行政部报销差旅费"
    )

    assert result.account_code == "6602"
    assert result.account_name == "管理费用"
    department_tags = [t for t in result.suggested_tags if t["category_code"] == "department"]
    assert len(department_tags) == 1
    assert department_tags[0]["tag_value"] == "行政部"


def test_resolve_requires_llm_flag():
    """当往来类科目存在下级段但无法识别维度且存在摘要时，标记需要 LLM 解析。"""
    result = resolve_account_for_import(
        "1122.01", "应收账款", "某笔业务往来"
    )

    assert result.account_code == "1122"
    assert result.account_name == "应收账款"
    assert result.requires_llm_resolution is True


def test_resolve_non_counterparty_account_no_counterparty():
    """非往来类科目不应从下级段推断往来单位。"""
    result = resolve_account_for_import(
        "5001.01", "生产成本-直接材料", "领用材料"
    )

    assert result.counterparty_name is None
    assert result.suggested_tags[0]["category_code"] == "cost_element"
