"""账簿会计时间线起点与首期种子化测试。"""
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _register_user(client: TestClient, username: str, phone: str | None = None) -> tuple[dict, int]:
    response = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "password": "testpass123",
            "phone": phone,
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me_response = client.get("/api/auth/me", headers=headers)
    assert me_response.status_code == 200
    return headers, me_response.json()["id"]


def test_create_ledger_defaults_timeline_to_today_and_seeds_open_period(client: TestClient):
    headers, _ = _register_user(client, "timeline_admin", "13800138200")
    team_response = client.post(
        "/api/teams",
        json={"name": "时间线团队", "type": "firm"},
        headers=headers,
    )
    team_id = team_response.json()["id"]

    ledger_response = client.post(
        "/api/ledgers",
        json={"team_id": team_id, "name": "默认时间线账簿"},
        headers=headers,
    )
    assert ledger_response.status_code == 200
    ledger = ledger_response.json()
    assert ledger["accounting_start_date"] == date.today().isoformat()

    client.post(f"/api/ledgers/{ledger['id']}/switch", headers=headers)
    periods_response = client.get(
        f"/api/accounting-periods?ledger_id={ledger['id']}",
        headers=headers,
    )
    assert periods_response.status_code == 200
    periods = periods_response.json()
    assert len(periods) == 1
    period = periods[0]
    today = date.today()
    assert period["period_code"] == f"{today.year:04d}-{today.month:02d}"
    assert period["status"] == "open"


def test_create_ledger_accepts_custom_accounting_start_date(client: TestClient):
    headers, _ = _register_user(client, "timeline_custom", "13800138201")
    team_response = client.post(
        "/api/teams",
        json={"name": "自定义时间线团队", "type": "firm"},
        headers=headers,
    )
    team_id = team_response.json()["id"]

    ledger_response = client.post(
        "/api/ledgers",
        json={
            "team_id": team_id,
            "name": "2025年补建账簿",
            "accounting_start_date": "2025-03-15",
        },
        headers=headers,
    )
    assert ledger_response.status_code == 200
    ledger = ledger_response.json()
    assert ledger["accounting_start_date"] == "2025-03-15"

    client.post(f"/api/ledgers/{ledger['id']}/switch", headers=headers)
    periods_response = client.get(
        f"/api/accounting-periods?ledger_id={ledger['id']}",
        headers=headers,
    )
    periods = periods_response.json()
    assert len(periods) == 1
    assert periods[0]["period_code"] == "2025-03"
    assert periods[0]["start_date"] == "2025-03-01"
    assert periods[0]["end_date"] == "2025-03-31"


def test_update_and_delete_ledger(client: TestClient):
    headers, _ = _register_user(client, "ledger_crud_admin", "13800138202")
    team_response = client.post(
        "/api/teams",
        json={"name": "CRUD团队", "type": "firm"},
        headers=headers,
    )
    team_id = team_response.json()["id"]

    ledger_response = client.post(
        "/api/ledgers",
        json={"team_id": team_id, "name": "待编辑账簿"},
        headers=headers,
    )
    ledger_id = ledger_response.json()["id"]

    update_response = client.put(
        f"/api/ledgers/{ledger_id}",
        json={"name": "已重命名账簿", "accounting_start_date": "2024-01-01"},
        headers=headers,
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == "已重命名账簿"
    assert updated["accounting_start_date"] == "2024-01-01"

    delete_response = client.post(
        f"/api/ledgers/{ledger_id}/delete",
        json={"reason": "测试删除"},
        headers=headers,
    )
    assert delete_response.status_code == 200
    deleted = delete_response.json()
    assert deleted["deleted"] is True
    assert deleted["ledger_id"] == ledger_id

    list_response = client.get("/api/ledgers", headers=headers)
    assert list_response.status_code == 200
    assert ledger_id not in [item["id"] for item in list_response.json()]


def test_initialize_ledger_clears_vouchers_keeps_ledger(client: TestClient):
    """初始化账簿应删除全部凭证与分录，但保留账簿、科目与期间。"""
    headers, _ = _register_user(client, "ledger_init_admin", "13800138203")
    team_response = client.post(
        "/api/teams",
        json={"name": "初始化团队", "type": "firm"},
        headers=headers,
    )
    team_id = team_response.json()["id"]

    ledger_response = client.post(
        "/api/ledgers",
        json={"team_id": team_id, "name": "待初始化账簿"},
        headers=headers,
    )
    ledger_id = ledger_response.json()["id"]
    client.post(f"/api/ledgers/{ledger_id}/switch", headers=headers)

    periods_response = client.get(
        f"/api/accounting-periods?ledger_id={ledger_id}",
        headers=headers,
    )
    periods = periods_response.json()
    assert len(periods) >= 1
    period = periods[0]
    period_id = period["id"]
    organization_id = period["organization_id"]
    voucher_date = period["start_date"]

    voucher_response = client.post(
        "/api/vouchers",
        json={
            "ledger_id": ledger_id,
            "organization_id": organization_id,
            "period_id": period_id,
            "voucher_type": "记",
            "voucher_number": "001",
            "voucher_date": voucher_date,
            "summary": "测试凭证",
            "lines": [
                {"line_no": 1, "summary": "办公费", "account_code": "6602", "debit_amount": "100.00", "credit_amount": "0.00"},
                {"line_no": 2, "summary": "银行存款", "account_code": "1002", "debit_amount": "0.00", "credit_amount": "100.00"},
            ],
        },
        headers=headers,
    )
    assert voucher_response.status_code == 201

    vouchers_before = client.get(
        f"/api/entries/vouchers?ledger_id={ledger_id}",
        headers=headers,
    )
    assert vouchers_before.status_code == 200
    assert vouchers_before.json()["total"] >= 1

    init_response = client.post(
        f"/api/ledgers/{ledger_id}/initialize",
        json={"reason": "测试初始化"},
        headers=headers,
    )
    assert init_response.status_code == 200
    init_data = init_response.json()
    assert init_data["ledger_id"] == ledger_id
    assert init_data["deleted_vouchers"] == 1
    assert init_data["deleted_entries"] >= 2

    vouchers_after = client.get(
        f"/api/entries/vouchers?ledger_id={ledger_id}",
        headers=headers,
    )
    assert vouchers_after.status_code == 200
    assert vouchers_after.json()["total"] == 0

    periods_after = client.get(
        f"/api/accounting-periods?ledger_id={ledger_id}",
        headers=headers,
    )
    assert periods_after.status_code == 200
    assert len(periods_after.json()) >= 1

    list_response = client.get("/api/ledgers", headers=headers)
    assert ledger_id in [item["id"] for item in list_response.json()]
    matched = next(item for item in list_response.json() if item["id"] == ledger_id)
    assert matched["name"] == "待初始化账簿"
