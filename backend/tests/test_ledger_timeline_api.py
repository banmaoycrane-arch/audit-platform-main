"""账套会计时间线起点与首期种子化测试。"""
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
        json={"team_id": team_id, "name": "默认时间线账套"},
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
            "name": "2025年补建账套",
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
