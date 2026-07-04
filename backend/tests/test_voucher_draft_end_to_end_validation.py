# -*- coding: utf-8 -*-
"""
模块功能：凭证草稿端到端验证测试。
业务场景：验证从候选凭证草稿确认到落库的完整流程，
         包括正常路径和各类异常场景。
政策依据：会计准则对记账凭证完整性、借贷平衡、会计期间控制的要求。
输入数据：候选凭证草稿列表、账簿、会计期间、科目表。
输出结果：落库的 Voucher 记录或结构化校验错误。
创建日期：2026-07-02
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import AccountingPeriod, ChartOfAccounts, Organization, Voucher
from app.db.session import Base, engine
from app.main import app
from app.models.ledger import Ledger
from app.models.team import Team
from app.models.user import User
from app.models.user_ledger_auth import UserLedgerAuth
from app.core.security import create_access_token
from app.services.basic_data.coa_service import init_default_accounts
from app.services.accounting.voucher_draft_validation_service import (
    DraftErrorCode,
    validate_voucher_drafts,
)


client = TestClient(app)


@pytest.fixture(scope="function")
def db_session():
    """测试用数据库会话。"""
    Base.metadata.create_all(bind=engine)
    session = Session(engine)
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session):
    """创建测试用户。"""
    user = User(
        username="test_accountant",
        phone="13800000000",
        email="test@example.com",
        hashed_password="fake_hash",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_team(db_session):
    """创建测试团队。"""
    team = Team(name="测试团队", type="enterprise")
    db_session.add(team)
    db_session.commit()
    db_session.refresh(team)
    return team


@pytest.fixture
def test_organization(db_session):
    """创建测试组织。"""
    org = Organization(name="测试企业")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture
def test_ledger(db_session, test_team, test_user, test_organization):
    """创建测试账簿并初始化科目（含 mapper 常用的二级科目）。"""
    ledger = Ledger(
        team_id=test_team.id,
        name="测试账簿",
        status="active",
        accounting_start_date=date(2024, 1, 1),
    )
    db_session.add(ledger)
    db_session.commit()
    db_session.refresh(ledger)

    auth = UserLedgerAuth(
        user_id=test_user.id,
        ledger_id=ledger.id,
        role="accountant",
    )
    db_session.add(auth)
    db_session.flush()

    init_default_accounts(db_session, ledger.id)

    # 补充 mapper 中使用的二级/三级明细科目
    extra_accounts = [
        {"code": "2221.01.02", "name": "应交税费-应交增值税-进项税额", "category": "liability", "direction": "credit", "parent_code": "2221.01"},
        {"code": "2221.01", "name": "应交税费-应交增值税", "category": "liability", "direction": "credit", "parent_code": "2221"},
        {"code": "6602.01", "name": "管理费用-差旅费", "category": "profit", "direction": "debit", "parent_code": "6602"},
        {"code": "2241.01", "name": "其他应付款-代扣个人所得税", "category": "liability", "direction": "credit", "parent_code": "2241"},
        {"code": "2241.02", "name": "其他应付款-代扣社保", "category": "liability", "direction": "credit", "parent_code": "2241"},
        {"code": "2241.03", "name": "其他应付款-代扣公积金", "category": "liability", "direction": "credit", "parent_code": "2241"},
    ]
    for item in extra_accounts:
        account = ChartOfAccounts(
            ledger_id=ledger.id,
            code=item["code"],
            name=item["name"],
            parent_code=item.get("parent_code"),
            level=2 if item["code"].count(".") == 1 else 3,
            category=item["category"],
            direction=item["direction"],
            is_terminal=True,
            status="active",
            is_system=False,
        )
        db_session.add(account)

    db_session.commit()
    return ledger


@pytest.fixture
def test_period_open(db_session, test_ledger, test_organization):
    """创建开放会计期间。"""
    period = AccountingPeriod(
        organization_id=test_organization.id,
        ledger_id=test_ledger.id,
        period_code="2024-01",
        period_type="monthly",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 31),
        status="open",
    )
    db_session.add(period)
    db_session.commit()
    db_session.refresh(period)
    return period


@pytest.fixture
def test_period_closed(db_session, test_ledger, test_organization):
    """创建已结账会计期间。"""
    period = AccountingPeriod(
        organization_id=test_organization.id,
        ledger_id=test_ledger.id,
        period_code="2023-12",
        period_type="monthly",
        start_date=date(2023, 12, 1),
        end_date=date(2023, 12, 31),
        status="closed",
    )
    db_session.add(period)
    db_session.commit()
    db_session.refresh(period)
    return period


@pytest.fixture
def auth_headers(test_user):
    """生成认证请求头。"""
    token = create_access_token({"sub": str(test_user.id)})
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# 测试数据构造辅助函数
# =============================================================================

def _build_draft(
    *,
    voucher_no: str = "记-0001",
    voucher_date: str = "2024-01-15",
    summary: str = "测试凭证",
    lines: list[dict] | None = None,
) -> dict:
    """构造一个候选凭证草稿。"""
    if lines is None:
        lines = [
            {"account_code": "6602", "account_name": "管理费用", "summary": "办公费", "debit_amount": "1000.00", "credit_amount": "0.00"},
            {"account_code": "1002", "account_name": "银行存款", "summary": "支付办公费", "debit_amount": "0.00", "credit_amount": "1000.00"},
        ]
    return {
        "voucher_no": voucher_no,
        "voucher_date": voucher_date,
        "summary": summary,
        "lines": lines,
    }


# =============================================================================
# 校验服务单元测试
# =============================================================================

class TestDraftValidationService:
    """凭证草稿校验服务单元测试。"""

    def test_valid_invoice_draft(self, db_session, test_ledger, test_period_open):
        """发票类型草稿校验通过。"""
        draft = _build_draft(
            voucher_no="记-0001",
            lines=[
                {"account_code": "1401", "account_name": "原材料", "summary": "采购", "debit_amount": "1000.00", "credit_amount": "0.00"},
                {"account_code": "2221.01.02", "account_name": "进项税额", "summary": "进项", "debit_amount": "130.00", "credit_amount": "0.00"},
                {"account_code": "2202", "account_name": "应付账款", "summary": "应付", "debit_amount": "0.00", "credit_amount": "1130.00"},
            ],
        )
        report = validate_voucher_drafts(
            db_session,
            ledger_id=test_ledger.id,
            organization_id=test_ledger.team_id,
            drafts=[draft],
        )
        assert report.is_valid is True

    def test_valid_bank_income_draft(self, db_session, test_ledger, test_period_open):
        """银行收款草稿校验通过。"""
        draft = _build_draft(
            voucher_no="银-0001",
            lines=[
                {"account_code": "1002", "account_name": "银行存款", "summary": "收款", "debit_amount": "5000.00", "credit_amount": "0.00"},
                {"account_code": "1122", "account_name": "应收账款", "summary": "收回欠款", "debit_amount": "0.00", "credit_amount": "5000.00"},
            ],
        )
        report = validate_voucher_drafts(
            db_session,
            ledger_id=test_ledger.id,
            organization_id=test_ledger.team_id,
            drafts=[draft],
        )
        assert report.is_valid is True

    def test_valid_bank_payment_draft(self, db_session, test_ledger, test_period_open):
        """银行付款草稿校验通过。"""
        draft = _build_draft(
            voucher_no="银-0002",
            lines=[
                {"account_code": "2202", "account_name": "应付账款", "summary": "付款", "debit_amount": "3000.00", "credit_amount": "0.00"},
                {"account_code": "1002", "account_name": "银行存款", "summary": "支付", "debit_amount": "0.00", "credit_amount": "3000.00"},
            ],
        )
        report = validate_voucher_drafts(
            db_session,
            ledger_id=test_ledger.id,
            organization_id=test_ledger.team_id,
            drafts=[draft],
        )
        assert report.is_valid is True

    def test_valid_expense_draft(self, db_session, test_ledger, test_period_open):
        """费用报销草稿校验通过。"""
        draft = _build_draft(
            voucher_no="费-0001",
            lines=[
                {"account_code": "6602.01", "account_name": "差旅费", "summary": "报销", "debit_amount": "800.00", "credit_amount": "0.00"},
                {"account_code": "1001", "account_name": "库存现金", "summary": "支付", "debit_amount": "0.00", "credit_amount": "800.00"},
            ],
        )
        report = validate_voucher_drafts(
            db_session,
            ledger_id=test_ledger.id,
            organization_id=test_ledger.team_id,
            drafts=[draft],
        )
        assert report.is_valid is True

    def test_valid_salary_draft(self, db_session, test_ledger, test_period_open):
        """工资发放草稿校验通过。"""
        draft = _build_draft(
            voucher_no="薪-0001",
            lines=[
                {"account_code": "2211", "account_name": "应付职工薪酬", "summary": "应发", "debit_amount": "100000.00", "credit_amount": "0.00"},
                {"account_code": "1002", "account_name": "银行存款", "summary": "实发", "debit_amount": "0.00", "credit_amount": "75000.00"},
                {"account_code": "2241.01", "account_name": "代扣个税", "summary": "个税", "debit_amount": "0.00", "credit_amount": "5000.00"},
                {"account_code": "2241.02", "account_name": "代扣社保", "summary": "社保", "debit_amount": "0.00", "credit_amount": "12000.00"},
                {"account_code": "2241.03", "account_name": "代扣公积金", "summary": "公积金", "debit_amount": "0.00", "credit_amount": "8000.00"},
            ],
        )
        report = validate_voucher_drafts(
            db_session,
            ledger_id=test_ledger.id,
            organization_id=test_ledger.team_id,
            drafts=[draft],
        )
        assert report.is_valid is True

    def test_valid_receipt_draft(self, db_session, test_ledger, test_period_open):
        """收据草稿校验通过。"""
        draft = _build_draft(
            voucher_no="收-0001",
            lines=[
                {"account_code": "1001", "account_name": "库存现金", "summary": "收押金", "debit_amount": "200.00", "credit_amount": "0.00"},
                {"account_code": "2241", "account_name": "其他应付款", "summary": "押金", "debit_amount": "0.00", "credit_amount": "200.00"},
            ],
        )
        report = validate_voucher_drafts(
            db_session,
            ledger_id=test_ledger.id,
            organization_id=test_ledger.team_id,
            drafts=[draft],
        )
        assert report.is_valid is True

    def test_unbalanced_draft(self, db_session, test_ledger, test_period_open):
        """借贷不平衡应被拒绝。"""
        draft = _build_draft(
            voucher_no="记-0002",
            lines=[
                {"account_code": "6602", "account_name": "管理费用", "summary": "办公费", "debit_amount": "1000.00", "credit_amount": "0.00"},
                {"account_code": "1002", "account_name": "银行存款", "summary": "支付", "debit_amount": "0.00", "credit_amount": "900.00"},
            ],
        )
        report = validate_voucher_drafts(
            db_session,
            ledger_id=test_ledger.id,
            organization_id=test_ledger.team_id,
            drafts=[draft],
        )
        assert report.is_valid is False
        assert any(e.code == DraftErrorCode.BALANCE_MISMATCH for e in report.errors)

    def test_negative_amount(self, db_session, test_ledger, test_period_open):
        """负数金额应被拒绝。"""
        draft = _build_draft(
            voucher_no="记-0003",
            lines=[
                {"account_code": "6602", "account_name": "管理费用", "summary": "办公费", "debit_amount": "-100.00", "credit_amount": "0.00"},
                {"account_code": "1002", "account_name": "银行存款", "summary": "支付", "debit_amount": "0.00", "credit_amount": "100.00"},
            ],
        )
        report = validate_voucher_drafts(
            db_session,
            ledger_id=test_ledger.id,
            organization_id=test_ledger.team_id,
            drafts=[draft],
        )
        assert report.is_valid is False
        assert any(e.code == DraftErrorCode.AMOUNT_NEGATIVE for e in report.errors)

    def test_empty_lines(self, db_session, test_ledger, test_period_open):
        """分录行少于 2 行应被拒绝。"""
        draft = _build_draft(voucher_no="记-0004", lines=[])
        report = validate_voucher_drafts(
            db_session,
            ledger_id=test_ledger.id,
            organization_id=test_ledger.team_id,
            drafts=[draft],
        )
        assert report.is_valid is False
        assert any(e.code == DraftErrorCode.LINES_TOO_FEW for e in report.errors)

    def test_account_not_found(self, db_session, test_ledger, test_period_open):
        """科目不存在应被拒绝。"""
        draft = _build_draft(
            voucher_no="记-0005",
            lines=[
                {"account_code": "9999", "account_name": "不存在科目", "summary": "错误", "debit_amount": "1000.00", "credit_amount": "0.00"},
                {"account_code": "1002", "account_name": "银行存款", "summary": "支付", "debit_amount": "0.00", "credit_amount": "1000.00"},
            ],
        )
        report = validate_voucher_drafts(
            db_session,
            ledger_id=test_ledger.id,
            organization_id=test_ledger.team_id,
            drafts=[draft],
        )
        assert report.is_valid is False
        assert any(e.code == DraftErrorCode.ACCOUNT_NOT_FOUND for e in report.errors)

    def test_voucher_no_duplicate_in_db(self, db_session, test_ledger, test_period_open):
        """与已有凭证号重复应被拒绝。"""
        existing_voucher = Voucher(
            ledger_id=test_ledger.id,
            organization_id=test_ledger.team_id,
            period_id=test_period_open.id,
            voucher_no="记-0006",
            voucher_date=date(2024, 1, 10),
            summary="已有凭证",
            status="draft",
            total_debit=Decimal("1000.00"),
            total_credit=Decimal("1000.00"),
        )
        db_session.add(existing_voucher)
        db_session.commit()

        draft = _build_draft(voucher_no="记-0006")
        report = validate_voucher_drafts(
            db_session,
            ledger_id=test_ledger.id,
            organization_id=test_ledger.team_id,
            drafts=[draft],
        )
        assert report.is_valid is False
        assert any(e.code == DraftErrorCode.VOUCHER_NO_DUPLICATE for e in report.errors)

    def test_voucher_no_duplicate_in_batch(self, db_session, test_ledger, test_period_open):
        """同批次凭证号重复应被拒绝。"""
        draft1 = _build_draft(voucher_no="记-0007")
        draft2 = _build_draft(voucher_no="记-0007")
        report = validate_voucher_drafts(
            db_session,
            ledger_id=test_ledger.id,
            organization_id=test_ledger.team_id,
            drafts=[draft1, draft2],
        )
        assert report.is_valid is False
        assert any(e.code == DraftErrorCode.VOUCHER_NO_DUPLICATE for e in report.errors)

    def test_period_closed(self, db_session, test_ledger, test_period_closed):
        """已结账期间应被拒绝。"""
        draft = _build_draft(voucher_no="记-0008", voucher_date="2023-12-15")
        report = validate_voucher_drafts(
            db_session,
            ledger_id=test_ledger.id,
            organization_id=test_ledger.team_id,
            drafts=[draft],
        )
        assert report.is_valid is False
        assert any(e.code == DraftErrorCode.PERIOD_CLOSED for e in report.errors)

    def test_date_outside_period(self, db_session, test_ledger, test_period_open):
        """凭证日期不在任何期间内应被拒绝。"""
        draft = _build_draft(voucher_no="记-0009", voucher_date="2025-06-15")
        report = validate_voucher_drafts(
            db_session,
            ledger_id=test_ledger.id,
            organization_id=test_ledger.team_id,
            drafts=[draft],
        )
        assert report.is_valid is False
        assert any(e.code == DraftErrorCode.PERIOD_NOT_FOUND for e in report.errors)


# =============================================================================
# Confirm API 集成测试
# =============================================================================

class TestConfirmDraftsAPI:
    """confirm-drafts 接口端到端测试。"""

    def test_confirm_valid_draft(self, db_session, test_ledger, test_period_open, auth_headers):
        """正常草稿确认后落库。"""
        payload = {
            "ledger_id": test_ledger.id,
            "organization_id": test_ledger.team_id,
            "drafts": [_build_draft(voucher_no="记-0010")],
        }
        response = client.post(
            "/api/parser-voucher/confirm-drafts",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["created_count"] == 1
        assert len(data["voucher_ids"]) == 1

        voucher = db_session.get(Voucher, data["voucher_ids"][0])
        assert voucher is not None
        assert voucher.status == "draft"
        assert voucher.period_id == test_period_open.id
        assert voucher.total_debit == Decimal("1000.00")
        assert voucher.total_credit == Decimal("1000.00")

    def test_confirm_rejects_invalid_draft(self, db_session, test_ledger, test_period_open, auth_headers):
        """校验失败时整张批次不落库。"""
        payload = {
            "ledger_id": test_ledger.id,
            "organization_id": test_ledger.team_id,
            "drafts": [
                _build_draft(voucher_no="记-0011"),
                _build_draft(
                    voucher_no="记-0012",
                    lines=[
                        {"account_code": "6602", "account_name": "管理费用", "summary": "办公费", "debit_amount": "1000.00", "credit_amount": "0.00"},
                        {"account_code": "1002", "account_name": "银行存款", "summary": "支付", "debit_amount": "0.00", "credit_amount": "900.00"},
                    ],
                ),
            ],
        }
        response = client.post(
            "/api/parser-voucher/confirm-drafts",
            json=payload,
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["created_count"] == 0
        assert len(data["errors"]) > 0
        assert data["voucher_ids"] == []

        # 验证没有任何凭证落库
        count = db_session.query(Voucher).filter(Voucher.ledger_id == test_ledger.id).count()
        assert count == 0

    def test_confirm_returns_structured_errors(self, db_session, test_ledger, test_period_open, auth_headers):
        """返回按 draft_index 的结构化错误。"""
        payload = {
            "ledger_id": test_ledger.id,
            "organization_id": test_ledger.team_id,
            "drafts": [
                _build_draft(voucher_no="记-0013"),
                _build_draft(
                    voucher_no="",
                    lines=[
                        {"account_code": "6602", "account_name": "管理费用", "summary": "办公费", "debit_amount": "1000.00", "credit_amount": "0.00"},
                        {"account_code": "1002", "account_name": "银行存款", "summary": "支付", "debit_amount": "0.00", "credit_amount": "1000.00"},
                    ],
                ),
            ],
        }
        response = client.post(
            "/api/parser-voucher/confirm-drafts",
            json=payload,
            headers=auth_headers,
        )
        data = response.json()
        assert data["success"] is False
        error = next(e for e in data["errors"] if e["draft_index"] == 1)
        assert error["code"] == DraftErrorCode.VOUCHER_NO_EMPTY

    def test_confirm_multiple_valid_drafts(self, db_session, test_ledger, test_period_open, auth_headers):
        """多张正常草稿批量落库。"""
        payload = {
            "ledger_id": test_ledger.id,
            "organization_id": test_ledger.team_id,
            "drafts": [
                _build_draft(voucher_no="记-0014"),
                _build_draft(
                    voucher_no="记-0015",
                    lines=[
                        {"account_code": "1401", "account_name": "原材料", "summary": "采购", "debit_amount": "2000.00", "credit_amount": "0.00"},
                        {"account_code": "2202", "account_name": "应付账款", "summary": "应付", "debit_amount": "0.00", "credit_amount": "2000.00"},
                    ],
                ),
            ],
        }
        response = client.post(
            "/api/parser-voucher/confirm-drafts",
            json=payload,
            headers=auth_headers,
        )
        data = response.json()
        assert data["success"] is True
        assert data["created_count"] == 2

        count = db_session.query(Voucher).filter(Voucher.ledger_id == test_ledger.id).count()
        assert count == 2
