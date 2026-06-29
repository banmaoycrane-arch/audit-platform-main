from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    AccountingEntry,
    AccountingPeriod,
    AuditFinding,
    AuditRisk,
    Entity,
    ImportJob,
    Organization,
)
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
            test_client._SessionLocal = TestingSessionLocal  # type: ignore[attr-defined]
            yield test_client
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _get_auth_headers(client: TestClient) -> dict:
    resp = client.post("/api/auth/register", json={"username": "testuser", "password": "testpass123", "agreed_terms": True, "agreed_privacy": True})
    assert resp.status_code == 200
    resp = client.post("/api/auth/login/password", json={"username": "testuser", "password": "testpass123"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_dashboard_summary_empty_returns_zeros(client):
    headers = _get_auth_headers(client)
    response = client.get("/api/dashboard/summary", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["voucher_count"] == 0
    assert data["unclosed_periods"] == 0
    assert data["pending_risks"] == 0
    assert data["user"]["username"] == "testuser"
    assert data["user"]["team"] is None


def test_dashboard_summary_with_data_returns_counts(client):
    headers = _get_auth_headers(client)
    SessionLocal = client._SessionLocal  # type: ignore[attr-defined]
    db = SessionLocal()
    try:
        org = Organization(name="测试企业")
        db.add(org)
        db.commit()
        db.refresh(org)

        job = ImportJob(organization_id=org.id, status="completed")
        db.add(job)
        db.commit()
        db.refresh(job)

        # 2 张凭证 (3 行分录，但 voucher_no 有 2 个)
        db.add_all([
            AccountingEntry(
                organization_id=org.id,
                import_job_id=job.id,
                voucher_no="V001",
                voucher_date=date(2026, 1, 15),
                debit_amount=100,
                credit_amount=0,
            ),
            AccountingEntry(
                organization_id=org.id,
                import_job_id=job.id,
                voucher_no="V001",
                voucher_date=date(2026, 1, 15),
                debit_amount=0,
                credit_amount=100,
            ),
            AccountingEntry(
                organization_id=org.id,
                import_job_id=job.id,
                voucher_no="V002",
                voucher_date=date(2026, 1, 16),
                debit_amount=200,
                credit_amount=0,
            ),
        ])

        # 2 个 open 期间 + 1 个 closed 期间
        db.add_all([
            AccountingPeriod(
                organization_id=org.id,
                period_code="2026-01",
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
                status="open",
            ),
            AccountingPeriod(
                organization_id=org.id,
                period_code="2026-02",
                start_date=date(2026, 2, 1),
                end_date=date(2026, 2, 28),
                status="open",
            ),
            AccountingPeriod(
                organization_id=org.id,
                period_code="2025-12",
                start_date=date(2025, 12, 1),
                end_date=date(2025, 12, 31),
                status="closed",
            ),
        ])

        # 2 个待复核风险 + 1 个已复核
        db.add_all([
            AuditRisk(
                organization_id=org.id,
                import_job_id=job.id,
                risk_type="cutoff",
                risk_level="high",
                title="跨期问题",
                description="期末凭证存在跨期",
                status="pending_review",
            ),
            AuditRisk(
                organization_id=org.id,
                import_job_id=job.id,
                risk_type="completeness",
                risk_level="medium",
                title="跳号",
                description="凭证号不连续",
                status="pending_review",
            ),
            AuditRisk(
                organization_id=org.id,
                import_job_id=job.id,
                risk_type="classification",
                risk_level="low",
                title="科目错配",
                description="已确认无影响",
                status="approved",
            ),
        ])

        # 1 个 finding
        db.add(
            AuditFinding(
                job_id=job.id,
                finding_uuid="f-001",
                finding_type="completeness",
                severity="high",
                finding_title="序时簿存在跳号",
                created_at=datetime.utcnow(),
            )
        )

        db.commit()
    finally:
        db.close()

    response = client.get("/api/dashboard/summary", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["voucher_count"] == 2
    assert data["unclosed_periods"] == 2
    assert data["pending_risks"] == 2
    assert data["module_status"]["ledger"]["pending_vouchers"] == 3
    assert data["module_status"]["audit"]["active_projects"] == 1


def test_dashboard_summary_returns_team_after_onboarding(client):
    headers = _get_auth_headers(client)
    team_response = client.post(
        "/api/teams",
        json={"name": "仪表盘团队", "type": "firm"},
        headers=headers,
    )
    assert team_response.status_code == 200
    team_id = team_response.json()["id"]

    ledger_response = client.post(
        "/api/ledgers",
        json={"team_id": team_id, "name": "仪表盘账簿"},
        headers=headers,
    )
    assert ledger_response.status_code == 200
    ledger_id = ledger_response.json()["id"]

    client.post(f"/api/ledgers/{ledger_id}/switch", headers=headers)
    client.post(
        "/api/projects",
        json={"team_id": team_id, "name": "仪表盘项目"},
        headers=headers,
    )

    SessionLocal = client._SessionLocal  # type: ignore[attr-defined]
    db = SessionLocal()
    try:
        db.add(
            Entity(
                entity_name="仪表盘会计主体",
                entity_type="company",
                entity_category="parent",
                is_accounting_entity=True,
                ledger_id=ledger_id,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/api/dashboard/summary",
        headers={**headers, "X-Ledger-Id": str(ledger_id)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["team"] == {"id": team_id, "name": "仪表盘团队"}
