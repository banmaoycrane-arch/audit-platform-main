"""凭证查询 API 测试。"""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import AccountingEntry, Organization
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
            yield test_client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _register(client: TestClient, username: str, phone: str) -> dict:
    resp = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "testpass123",
            "phone": phone,
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_voucher_query_line_mode_returns_cards(client):
    test_client, db_factory = client
    headers = _register(test_client, "voucher_query_user", "13800139101")

    team = test_client.post("/api/teams", json={"name": "凭证查询团队", "type": "firm"}, headers=headers).json()
    ledger = test_client.post(
        "/api/ledgers",
        json={"team_id": team["id"], "name": "凭证查询账簿"},
        headers=headers,
    ).json()

    db = db_factory()
    org = Organization(name="查询企业", fiscal_year=2026)
    db.add(org)
    db.flush()
    org_id = org.id
    db.add_all(
        [
            AccountingEntry(
                organization_id=org_id,
                import_job_id=1,
                ledger_id=ledger["id"],
                voucher_no="记-001",
                voucher_date=date(2026, 2, 1),
                summary="办公费",
                account_code="6602",
                account_name="管理费用",
                debit_amount=100,
                credit_amount=0,
                normalized_text="记-001",
                entry_line_no=1,
            ),
            AccountingEntry(
                organization_id=org_id,
                import_job_id=1,
                ledger_id=ledger["id"],
                voucher_no="记-001",
                voucher_date=date(2026, 2, 1),
                summary="银行存款",
                account_code="1002",
                account_name="银行存款",
                debit_amount=0,
                credit_amount=100,
                normalized_text="记-001",
                entry_line_no=2,
            ),
        ]
    )
    db.commit()
    db.close()

    resp = test_client.get(
        f"/api/entries/vouchers?ledger_id={ledger['id']}&account_code=6602",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["voucher_no"] == "记-001"
    assert body["items"][0]["line_count"] == 2


def test_voucher_query_voucher_mode_filters_totals(client):
    test_client, db_factory = client
    headers = _register(test_client, "voucher_total_user", "13800139102")

    team = test_client.post("/api/teams", json={"name": "合计筛选团队", "type": "firm"}, headers=headers).json()
    ledger = test_client.post(
        "/api/ledgers",
        json={"team_id": team["id"], "name": "合计筛选账簿"},
        headers=headers,
    ).json()

    db = db_factory()
    org = Organization(name="合计企业", fiscal_year=2026)
    db.add(org)
    db.flush()
    org_id = org.id
    db.add_all(
        [
            AccountingEntry(
                organization_id=org_id,
                import_job_id=1,
                ledger_id=ledger["id"],
                voucher_no="收-001",
                voucher_date=date(2026, 2, 5),
                summary="收款",
                account_code="1002",
                account_name="银行存款",
                debit_amount=5000,
                credit_amount=0,
                normalized_text="收-001",
                entry_line_no=1,
            ),
            AccountingEntry(
                organization_id=org_id,
                import_job_id=1,
                ledger_id=ledger["id"],
                voucher_no="收-001",
                voucher_date=date(2026, 2, 5),
                summary="主营业务收入",
                account_code="6001",
                account_name="主营业务收入",
                debit_amount=0,
                credit_amount=5000,
                normalized_text="收-001",
                entry_line_no=2,
            ),
        ]
    )
    db.commit()
    db.close()

    resp = test_client.get(
        f"/api/entries/vouchers?ledger_id={ledger['id']}&filter_mode=voucher&total_min=4000",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["credit_total"] == 5000


def test_list_entries_rejects_limit_above_500(client):
    test_client, _ = client
    headers = _register(test_client, "entry_limit_user", "13800139201")
    team = test_client.post("/api/teams", json={"name": "分录限额团队", "type": "firm"}, headers=headers).json()
    ledger = test_client.post(
        "/api/ledgers",
        json={"team_id": team["id"], "name": "分录限额账簿"},
        headers=headers,
    ).json()

    resp = test_client.get(f"/api/entries?ledger_id={ledger['id']}&limit=501", headers=headers)
    assert resp.status_code == 422


def test_voucher_query_rejects_limit_above_500(client):
    test_client, _ = client
    headers = _register(test_client, "voucher_limit_user", "13800139204")
    team = test_client.post("/api/teams", json={"name": "凭证限额团队", "type": "firm"}, headers=headers).json()
    ledger = test_client.post(
        "/api/ledgers",
        json={"team_id": team["id"], "name": "凭证限额账簿"},
        headers=headers,
    ).json()

    resp = test_client.get(
        f"/api/entries/vouchers?ledger_id={ledger['id']}&limit=501",
        headers=headers,
    )
    assert resp.status_code == 422


def test_voucher_query_returns_up_to_500_vouchers_per_page(client):
    test_client, db_factory = client
    headers = _register(test_client, "voucher_page_cap", "13800139203")
    team = test_client.post("/api/teams", json={"name": "凭证分页团队", "type": "firm"}, headers=headers).json()
    ledger = test_client.post(
        "/api/ledgers",
        json={"team_id": team["id"], "name": "凭证分页账簿"},
        headers=headers,
    ).json()

    db = db_factory()
    org = Organization(name="分页企业", fiscal_year=2026)
    db.add(org)
    db.flush()
    org_id = org.id
    entries = []
    for index in range(520):
        voucher_no = f"记-{index:04d}"
        voucher_day = date(2026, 2, 1)
        entries.extend(
            [
                AccountingEntry(
                    organization_id=org_id,
                    import_job_id=1,
                    ledger_id=ledger["id"],
                    voucher_no=voucher_no,
                    voucher_date=voucher_day,
                    summary="借方",
                    account_code="6601",
                    account_name="销售费用",
                    debit_amount=1,
                    credit_amount=0,
                    normalized_text=voucher_no,
                    entry_line_no=1,
                ),
                AccountingEntry(
                    organization_id=org_id,
                    import_job_id=1,
                    ledger_id=ledger["id"],
                    voucher_no=voucher_no,
                    voucher_date=voucher_day,
                    summary="贷方",
                    account_code="1002",
                    account_name="银行存款",
                    debit_amount=0,
                    credit_amount=1,
                    normalized_text=voucher_no,
                    entry_line_no=2,
                ),
            ]
        )
    db.add_all(entries)
    db.commit()
    db.close()

    resp = test_client.get(
        f"/api/entries/vouchers?ledger_id={ledger['id']}&limit=500&offset=0",
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 520
    assert len(body["items"]) == 500

    page2 = test_client.get(
        f"/api/entries/vouchers?ledger_id={ledger['id']}&limit=500&offset=500",
        headers=headers,
    )
    assert page2.status_code == 200
    assert len(page2.json()["items"]) == 20
