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


def _auth_headers(client: TestClient, username: str) -> dict:
    reg = client.post(
        "/api/auth/register",
        json={
            "username": username,
            "phone": f"138{username[-8:]}",
            "password": "testpass123",
            "agreed_terms": True,
            "agreed_privacy": True,
        },
    )
    token = reg.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_import_jobs_reuse_organization_for_same_ledger(client):
    headers = _auth_headers(client, "ledger_org_user")
    team = client.post("/api/teams", json={"name": "组织复用团队", "type": "company"}, headers=headers)
    ledger = client.post(
        "/api/ledgers",
        json={"team_id": team.json()["id"], "name": "组织复用账簿"},
        headers=headers,
    )
    ledger_id = ledger.json()["id"]

    job1 = client.post(
        "/api/import-jobs",
        json={"organization_name": "第一次导入", "ledger_id": ledger_id},
        headers=headers,
    )
    job2 = client.post(
        "/api/import-jobs",
        json={"organization_name": "第二次导入", "ledger_id": ledger_id},
        headers=headers,
    )

    assert job1.status_code == 200
    assert job2.status_code == 200
    assert job1.json()["organization_id"] == job2.json()["organization_id"]


def test_list_periods_can_filter_by_ledger_id(client):
    headers = _auth_headers(client, "ledger_period_user")
    team = client.post("/api/teams", json={"name": "期间团队", "type": "company"}, headers=headers)
    ledger = client.post(
        "/api/ledgers",
        json={"team_id": team.json()["id"], "name": "期间账簿"},
        headers=headers,
    )
    ledger_id = ledger.json()["id"]
    job = client.post(
        "/api/import-jobs",
        json={"organization_name": "期间账簿", "ledger_id": ledger_id},
        headers=headers,
    )
    org_id = job.json()["organization_id"]
    created = client.post(
        "/api/accounting-periods",
        json={
            "organization_id": org_id,
            "ledger_id": ledger_id,
            "period_code": "2027-01",
            "start_date": "2027-01-01",
            "end_date": "2027-01-31",
        },
        headers=headers,
    )
    assert created.status_code == 200

    listed = client.get(f"/api/accounting-periods?ledger_id={ledger_id}", headers=headers)
    assert listed.status_code == 200
    assert any(item["period_code"] == "2027-01" for item in listed.json())
