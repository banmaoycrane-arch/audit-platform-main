from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import AccountingPeriod, Organization
from app.db.session import Base, get_db
from app.main import app


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            test_client.test_engine = engine
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def test_empty_accounts_can_be_listed(client):
    response = client.get("/api/coa")
    assert response.status_code == 200
    assert response.json() == []


def test_manual_entry_base_data_endpoints_return_clear_responses(client):
    with next(app.dependency_overrides[get_db]()) as db:
        organization = Organization(name="基础资料测试企业")
        db.add(organization)
        db.flush()
        db.add(
            AccountingPeriod(
                organization_id=organization.id,
                period_code="2026-06",
                period_type="monthly",
                start_date=date(2026, 6, 1),
                end_date=date(2026, 6, 30),
                status="open",
            )
        )
        db.commit()

    periods = client.get("/api/accounting-periods")
    assert periods.status_code == 200
    assert periods.json()[0]["period_code"] == "2026-06"

    accounts = client.get("/api/coa")
    assert accounts.status_code == 200
    assert isinstance(accounts.json(), list)

    counterparties = client.get("/api/counterparties")
    assert counterparties.status_code == 200
    assert isinstance(counterparties.json(), list)


def test_basic_data_lists_return_business_error_when_schema_is_incomplete(client):
    with client.test_engine.begin() as connection:
        connection.execute(text("DROP TABLE chart_of_accounts"))
        connection.execute(text("DROP TABLE counterparties"))

    accounts_response = client.get("/api/coa")
    assert accounts_response.status_code == 422
    assert "会计科目加载失败" in accounts_response.json()["detail"]

    counterparties_response = client.get("/api/counterparties")
    assert counterparties_response.status_code == 422
    assert "往来单位加载失败" in counterparties_response.json()["detail"]


def test_system_account_cannot_be_deleted(client):
    from app.db.models import ChartOfAccounts

    with next(app.dependency_overrides[get_db]()) as db:
        db.add(
            ChartOfAccounts(
                code="1002",
                name="银行存款",
                category="asset",
                direction="debit",
                is_system=True,
            )
        )
        db.commit()

    resp = client.delete("/api/coa/1002")
    assert resp.status_code == 400
    assert "不可删除" in resp.json()["detail"]


def test_create_and_delete_custom_account(client):
    client.get("/api/coa")
    resp = client.post(
        "/api/coa",
        json={
            "code": "9999",
            "name": "自定义往来",
            "category": "asset",
            "direction": "debit",
            "account_category": "资产",
            "account_subcategory": "流动资产",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_system"] is False
    assert data["account_category"] == "资产"
    assert data["account_subcategory"] == "流动资产"
    assert data["equity_subcategory"] is None
    assert data["include_in_dividend_base"] is None

    delete = client.delete("/api/coa/9999")
    assert delete.status_code == 200
    assert delete.json() == {"deleted": "9999"}


def test_create_liability_account_returns_design_fields(client):
    resp = client.post(
        "/api/coa",
        json={
            "code": "2999",
            "name": "自定义长期应付款",
            "category": "liability",
            "direction": "credit",
            "account_category": "负债",
            "account_subcategory": "长期负债",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["account_category"] == "负债"
    assert data["account_subcategory"] == "长期负债"
    assert data["equity_subcategory"] is None
    assert data["include_in_dividend_base"] is None


def test_create_equity_account_non_dividend_default_false(client):
    resp = client.post(
        "/api/coa",
        json={
            "code": "4099",
            "name": "自定义资本公积",
            "category": "equity",
            "direction": "credit",
            "account_category": "所有者权益",
            "equity_subcategory": "资本公积",
            "include_in_dividend_base": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["account_category"] == "所有者权益"
    assert data["account_subcategory"] is None
    assert data["equity_subcategory"] == "资本公积"
    assert data["include_in_dividend_base"] is False


def test_create_retained_earnings_dividend_base_default_true(client):
    resp = client.post(
        "/api/coa",
        json={
            "code": "4105",
            "name": "未分配利润-自定义",
            "category": "equity",
            "direction": "credit",
            "account_category": "所有者权益",
            "equity_subcategory": "未分配利润",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["equity_subcategory"] == "未分配利润"
    assert data["include_in_dividend_base"] is True


def test_create_retained_earnings_dividend_base_can_be_false(client):
    resp = client.post(
        "/api/coa",
        json={
            "code": "4106",
            "name": "未分配利润-受限",
            "category": "equity",
            "direction": "credit",
            "account_category": "所有者权益",
            "equity_subcategory": "未分配利润",
            "include_in_dividend_base": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["equity_subcategory"] == "未分配利润"
    assert data["include_in_dividend_base"] is False


def test_disable_and_archive(client):
    client.post(
        "/api/coa",
        json={
            "code": "1002",
            "name": "银行存款",
            "category": "asset",
            "direction": "debit",
            "account_category": "资产",
            "account_subcategory": "流动资产",
        },
    )
    resp = client.post("/api/coa/1002/disable")
    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"

    resp2 = client.post("/api/coa/1002/archive")
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "archived"


def test_counterparty_crud(client):
    create = client.post(
        "/api/counterparties",
        json={"name": "A公司", "role": "customer"},
    )
    assert create.status_code == 200
    cp_id = create.json()["id"]

    listing = client.get("/api/counterparties").json()
    assert any(c["id"] == cp_id for c in listing)

    update = client.put(
        f"/api/counterparties/{cp_id}",
        json={"role": "supplier"},
    )
    assert update.status_code == 200
    assert update.json()["role"] == "supplier"

    disable = client.post(f"/api/counterparties/{cp_id}/disable")
    assert disable.status_code == 200
    assert disable.json()["is_active"] is False


def test_counterparty_invalid_role(client):
    resp = client.post(
        "/api/counterparties",
        json={"name": "X", "role": "bad-role"},
    )
    assert resp.status_code == 400
