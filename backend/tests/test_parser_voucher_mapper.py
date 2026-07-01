# -*- coding: utf-8 -*-
"""
测试 parser_voucher_mapper 的映射逻辑
验证解析结果到候选凭证草稿的转换正确性
"""

import pytest
from decimal import Decimal
from datetime import datetime

from app.services.parser_engine.parse_result import (
    ParseResult,
    DocumentType,
    EngineType,
)
from app.services.parser_voucher_mapper import (
    parse_result_to_voucher_drafts,
    CandidateVoucherDraft,
)


class TestInvoiceMapping:
    """发票映射测试"""

    def test_invoice_with_tax(self):
        """测试含税发票映射：借存货+借进项税=贷应付账款"""
        parse_result = ParseResult(
            document_type=DocumentType.INVOICE,
            data={
                "invoice_no": "INV001",
                "seller_name": "测试供应商",
                "amount_excl_tax": 1000.00,
                "tax_amount": 130.00,
                "total_amount": 1130.00,
                "invoice_date": "2026-07-02",
            },
            confidence=0.95,
            engine=EngineType.RULE,
        )

        drafts = parse_result_to_voucher_drafts(parse_result)

        assert len(drafts) == 1
        draft = drafts[0]
        assert draft.document_type == "invoice"
        assert draft.voucher_no.startswith("记-")
        assert len(draft.lines) == 3  # 存货 + 进项税 + 应付账款

        # 验证借贷平衡
        debit_total = sum(line.debit_amount for line in draft.lines)
        credit_total = sum(line.credit_amount for line in draft.lines)
        assert debit_total == credit_total == Decimal("1130.00")
        assert len(draft.validation_errors) == 0

    def test_invoice_without_tax(self):
        """测试无税额发票：只有借存货+贷应付账款"""
        parse_result = ParseResult(
            document_type=DocumentType.INVOICE,
            data={
                "seller_name": "小规模供应商",
                "amount_excl_tax": 500.00,
                "tax_amount": 0,
                "total_amount": 500.00,
            },
            confidence=0.80,
        )

        drafts = parse_result_to_voucher_drafts(parse_result)
        assert len(drafts) == 1
        assert len(drafts[0].lines) == 2  # 无进项税行


class TestBankStatementMapping:
    """银行流水映射测试"""

    def test_income_transaction(self):
        """测试收款交易：借银行存款=贷应收账款"""
        parse_result = ParseResult(
            document_type=DocumentType.BANK_STATEMENT,
            data={
                "bank_name": "工商银行",
                "counterparty_name": "客户A",
                "transaction_amount": 5000.00,
                "transaction_date": "2026-07-01",
                "summary": "货款",
            },
            confidence=0.90,
        )

        drafts = parse_result_to_voucher_drafts(parse_result)
        assert len(drafts) == 1
        draft = drafts[0]
        assert draft.document_type == "bank_statement"
        assert len(draft.lines) == 2

        # 收款：第一行借银行存款
        assert draft.lines[0].account_code == "1002"
        assert draft.lines[0].debit_amount == Decimal("5000.00")
        # 第二行贷应收账款
        assert draft.lines[1].account_code == "1122"
        assert draft.lines[1].credit_amount == Decimal("5000.00")

    def test_payment_transaction(self):
        """测试付款交易：借应付账款=贷银行存款"""
        parse_result = ParseResult(
            document_type=DocumentType.BANK_STATEMENT,
            data={
                "bank_name": "建设银行",
                "counterparty_name": "供应商B",
                "transaction_amount": -3000.00,
                "summary": "支付货款",
            },
            confidence=0.85,
        )

        drafts = parse_result_to_voucher_drafts(parse_result)
        assert len(drafts) == 1

        # 付款：第一行借应付账款
        assert drafts[0].lines[0].account_code == "2202"
        assert drafts[0].lines[0].debit_amount == Decimal("3000.00")
        # 第二行贷银行存款
        assert drafts[0].lines[1].account_code == "1002"
        assert drafts[0].lines[1].credit_amount == Decimal("3000.00")


class TestExpenseMapping:
    """费用报销映射测试"""

    def test_travel_expense(self):
        """测试差旅费报销：借管理费用-差旅费=贷库存现金"""
        parse_result = ParseResult(
            document_type=DocumentType.EXPENSE_DOCUMENT,
            data={
                "reimburser_name": "张三",
                "expense_type": "差旅费",
                "total_amount": 800.00,
                "reimbursement_date": "2026-07-02",
            },
            confidence=0.88,
        )

        drafts = parse_result_to_voucher_drafts(parse_result)
        assert len(drafts) == 1
        draft = drafts[0]
        assert draft.lines[0].account_code == "6602.01"
        assert draft.lines[0].account_name == "管理费用-差旅费"
        assert draft.lines[0].debit_amount == Decimal("800.00")
        assert draft.lines[1].account_code == "1001"  # 库存现金
        assert draft.lines[1].credit_amount == Decimal("800.00")


class TestSalaryMapping:
    """工资表映射测试"""

    def test_salary_with_deductions(self):
        """测试含代扣项的工资发放"""
        parse_result = ParseResult(
            document_type=DocumentType.SALARY_TABLE,
            data={
                "salary_period": "2026-06",
                "total_salary": 100000.00,
                "total_personal_income_tax": 5000.00,
                "total_social_insurance": 12000.00,
                "total_housing_fund": 8000.00,
                "total_net_pay": 75000.00,
            },
            confidence=0.92,
        )

        drafts = parse_result_to_voucher_drafts(parse_result)
        assert len(drafts) == 1
        draft = drafts[0]
        assert len(draft.lines) == 5  # 应发 + 实发 + 个税 + 社保 + 公积金

        # 借方合计 = 应发工资
        debit_total = sum(line.debit_amount for line in draft.lines)
        assert debit_total == Decimal("100000.00")

        # 贷方合计 = 实发 + 个税 + 社保 + 公积金
        credit_total = sum(line.credit_amount for line in draft.lines)
        assert credit_total == Decimal("100000.00")

        # 借贷平衡
        assert len(draft.validation_errors) == 0


class TestReceiptMapping:
    """收据映射测试"""

    def test_basic_receipt(self):
        """测试基本收据映射"""
        parse_result = ParseResult(
            document_type=DocumentType.RECEIPT,
            data={
                "payee_name": "收款方",
                "payer_name": "付款方",
                "amount": 200.00,
                "reason": "押金",
                "date": "2026-07-02",
            },
            confidence=0.75,
        )

        drafts = parse_result_to_voucher_drafts(parse_result)
        assert len(drafts) == 1
        assert drafts[0].lines[0].debit_amount == Decimal("200.00")
        assert drafts[0].lines[1].credit_amount == Decimal("200.00")


class TestUnsupportedType:
    """不支持的文档类型测试"""

    def test_contract_returns_empty(self):
        """合同类型暂不支持，返回空列表"""
        parse_result = ParseResult(
            document_type=DocumentType.CONTRACT,
            data={"contract_name": "测试合同"},
            confidence=0.50,
        )

        drafts = parse_result_to_voucher_drafts(parse_result)
        assert len(drafts) == 0

    def test_empty_data_returns_empty(self):
        """空数据返回空列表"""
        parse_result = ParseResult(
            document_type=DocumentType.INVOICE,
            data={},
            confidence=0.0,
        )

        drafts = parse_result_to_voucher_drafts(parse_result)
        assert len(drafts) == 0


class TestDecimalPrecision:
    """金额精度测试"""

    def test_decimal_not_float(self):
        """确保金额使用 Decimal 而非 float"""
        parse_result = ParseResult(
            document_type=DocumentType.INVOICE,
            data={
                "seller_name": "精度测试",
                "amount_excl_tax": "1000.00",
                "tax_amount": "130.00",
                "total_amount": "1130.00",
            },
            confidence=0.90,
        )

        drafts = parse_result_to_voucher_drafts(parse_result)
        for line in drafts[0].lines:
            assert isinstance(line.debit_amount, Decimal)
            assert isinstance(line.credit_amount, Decimal)
