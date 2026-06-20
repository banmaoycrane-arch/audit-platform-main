import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    AuditFinding,
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
            yield test_client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)


def _seed_job_with_findings(TestingSessionLocal):
    db = TestingSessionLocal()
    try:
        org = Organization(name="审计导出测试企业", fiscal_year=2026)
        db.add(org)
        db.flush()
        job = ImportJob(organization_id=org.id, status="completed", entry_count=1, file_count=1)
        db.add(job)
        db.flush()
        db.add(
            AuditFinding(
                job_id=job.id,
                finding_uuid="uuid-export-1",
                finding_type="ghost_invoice",
                severity="high",
                business_type="purchase",
                finding_title="幽灵发票",
                finding_description="发票缺乏真实业务支撑",
                audit_procedure="逆查程序",
                audit_conclusion="无法证实其真实业务背景",
                risk_statement="可能存在虚开发票",
                recommendation="补充入库单与合同",
                related_entries=["entry-1"],
                related_files=["发票A.pdf"],
                finding_metadata={},
                status="pending",
            )
        )
        db.commit()
        return job.id
    finally:
        db.close()


def test_export_xlsx_returns_200(client):
    test_client, TestingSessionLocal = client
    job_id = _seed_job_with_findings(TestingSessionLocal)

    response = test_client.get(f"/api/audit-tests/{job_id}/export?format=xlsx")
    assert response.status_code == 200
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert f"audit_report_{job_id}.xlsx" in response.headers["content-disposition"]
    # xlsx 文件以 PK 开头（zip 容器）
    assert response.content[:2] == b"PK"
    assert len(response.content) > 100


def test_export_json_returns_200_with_findings(client):
    test_client, TestingSessionLocal = client
    job_id = _seed_job_with_findings(TestingSessionLocal)

    response = test_client.get(f"/api/audit-tests/{job_id}/export?format=json")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    payload = json.loads(response.content.decode("utf-8"))
    assert "summary" in payload
    assert "findings" in payload
    assert payload["summary"]["total_findings"] == 1
    assert payload["findings"][0]["finding_title"] == "幽灵发票"


def test_export_unknown_format_returns_400(client):
    test_client, TestingSessionLocal = client
    job_id = _seed_job_with_findings(TestingSessionLocal)

    response = test_client.get(f"/api/audit-tests/{job_id}/export?format=docx")
    assert response.status_code == 400
    assert "不支持的导出格式" in response.json()["detail"]


def test_export_unknown_job_returns_404(client):
    test_client, _ = client

    response = test_client.get("/api/audit-tests/9999/export?format=xlsx")
    assert response.status_code == 404
    assert response.json()["detail"] == "导入任务不存在"
