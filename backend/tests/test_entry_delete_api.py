"""凭证批量删除 API 测试。"""
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


def _seed_entries(db_factory, ledger_id: int, org_id: int) -> None:
    db = db_factory()
    try:
        entries = [
            AccountingEntry(
                organization_id=org_id,
                import_job_id=1,
                ledger_id=ledger_id,
                voucher_no="记-010",
                voucher_date=date(2026, 2, 3),
                summary="报销差旅费",
                account_code="6601",
                account_name="销售费用",
                debit_amount=800,
                credit_amount=0,
                normalized_text="记-010",
                entry_line_no=1,
            ),
            AccountingEntry(
                organization_id=org_id,
                import_job_id=1,
                ledger_id=ledger_id,
                voucher_no="记-010",
                voucher_date=date(2026, 2, 3),
                summary="报销差旅费",
                account_code="1002",
                account_name="银行存款",
                debit_amount=0,
                credit_amount=800,
                normalized_text="记-010",
                entry_line_no=2,
            ),
            AccountingEntry(
                organization_id=org_id,
                import_job_id=1,
                ledger_id=ledger_id,
                voucher_no="收-020",
                voucher_date=date(2026, 2, 8),
                summary="收服务费",
                account_code="1002",
                account_name="银行存款",
                debit_amount=5000,
                credit_amount=0,
                normalized_text="收-020",
                entry_line_no=1,
            ),
        ]
        db.add_all(entries)
        db.commit()
    finally:
        db.close()


def test_batch_delete_vouchers_removes_all_lines(client):
    test_client, db_factory = client
    headers = _register(test_client, "delete_user", "13800001001")

    team = test_client.post("/api/teams", json={"name": "删除测试团队", "type": "firm"}, headers=headers).json()
    ledger = test_client.post(
        "/api/ledgers",
        json={"team_id": team["id"], "name": "删除测试账簿"},
        headers=headers,
    ).json()
    ledger_id = ledger["id"]
    db = db_factory()
    org = Organization(name="删除测试企业", fiscal_year=2026)
    db.add(org)
    db.flush()
    org_id = org.id
    db.close()
    _seed_entries(db_factory, ledger_id, org_id)

    resp = test_client.post(
        "/api/entries/vouchers/batch-delete",
        headers=headers,
        json={
            "ledger_id": ledger_id,
            "vouchers": [{"voucher_no": "记-010", "voucher_date": "2026-02-03"}],
        },
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["deleted_vouchers"] == 1
    assert payload["deleted_entries"] == 2

    list_resp = test_client.get(f"/api/entries?ledger_id={ledger_id}", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] == 1


def test_batch_delete_is_all_or_nothing(client):
    test_client, db_factory = client
    headers = _register(test_client, "delete_user2", "13800001002")

    team = test_client.post("/api/teams", json={"name": "删除测试团队2", "type": "firm"}, headers=headers).json()
    ledger = test_client.post(
        "/api/ledgers",
        json={"team_id": team["id"], "name": "删除测试账簿2"},
        headers=headers,
    ).json()
    ledger_id = ledger["id"]
    db = db_factory()
    org = Organization(name="删除测试企业", fiscal_year=2026)
    db.add(org)
    db.flush()
    org_id = org.id
    db.close()
    _seed_entries(db_factory, ledger_id, org_id)

    resp = test_client.post(
        "/api/entries/vouchers/batch-delete",
        headers=headers,
        json={
            "ledger_id": ledger_id,
            "vouchers": [
                {"voucher_no": "记-010", "voucher_date": "2026-02-03"},
                {"voucher_no": "不存在", "voucher_date": "2026-02-03"},
            ],
        },
    )
    assert resp.status_code == 400

    list_resp = test_client.get(f"/api/entries?ledger_id={ledger_id}", headers=headers)
    assert list_resp.json()["total"] == 3
