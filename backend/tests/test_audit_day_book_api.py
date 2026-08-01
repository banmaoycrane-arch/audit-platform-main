# -*- coding: utf-8 -*-
"""
序时簿导入 API 单元测试。

业务场景：验证 /api/import-jobs 接口的序时簿导入能力，包括：
    1. 创建导入任务（ledger_day_book / audit_day_book）
    2. 上传序时簿文件
    3. 同步处理导入
    4. 获取检测报告（跳号、借贷平衡、完整性评分）
    5. 获取期间推荐

政策依据：符合《企业会计准则》对记账凭证完整性、借贷平衡的要求。

创建日期：2026-07-02
"""
import os
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes_imports import _import_reports
from app.db.models import AccountingEntry, StagingAccountingEntry
from app.db.session import Base, get_db
from app.main import app
from app.models.ledger import Ledger
from app.models.team import Team

from tests.conftest import register_auth_headers


@pytest.fixture
def client(monkeypatch, tmp_path):
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

    monkeypatch.setattr("app.storage.local_storage.get_settings", lambda: SimpleNamespace(upload_dir=str(tmp_path)))
    monkeypatch.setattr("app.services.doc_parsing.import_service.safe_vector_store", lambda: None)
    monkeypatch.setattr("app.services.audit.risk_case_library.safe_vector_store", lambda: None)
    monkeypatch.setattr("app.services.audit.risk_rule_service.safe_vector_store", lambda: None)
    monkeypatch.setattr("app.services.audit.audit_day_book_service.safe_vector_store", lambda: None)
    monkeypatch.setattr("app.services.accounting.entry_tag_vector_service.safe_vector_store", lambda: None)
    _import_reports.clear()
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            test_client._auth_headers = register_auth_headers(test_client)
            yield test_client, TestingSessionLocal
    finally:
        app.dependency_overrides.clear()
        _import_reports.clear()
        Base.metadata.drop_all(bind=engine)


def _seed_ledger(TestingSessionLocal, test_client):
    """创建测试账簿，并给当前测试用户授权管理员权限。"""
    from app.core.security import decode_token
    from app.models.user_ledger_auth import UserLedgerAuth

    token = test_client._auth_headers.get("Authorization", "").replace("Bearer ", "")
    payload = decode_token(token)
    user_id = int(payload["sub"])

    db = TestingSessionLocal()
    try:
        team = Team(name="序时簿测试团队")
        db.add(team)
        db.flush()
        ledger = Ledger(name="序时簿测试账簿", team_id=team.id)
        db.add(ledger)
        db.flush()
        auth = UserLedgerAuth(user_id=user_id, ledger_id=ledger.id, role="admin")
        db.add(auth)
        db.commit()
        return ledger.id
    finally:
        db.close()


def _acknowledge_dimension_readiness(test_client, ledger_id: int) -> None:
    """确认账簿维度规则已审阅，允许结构化导入。"""
    ack_response = test_client.post(
        f"/api/config/ledgers/{ledger_id}/dimension-readiness/acknowledge",
        headers=test_client._auth_headers,
    )
    assert ack_response.status_code == 200


def _review_all_staging(test_client, job_id: int, review_status: str = "verified") -> dict:
    response = test_client.post(
        f"/api/import-jobs/{job_id}/preview-entries/review-all",
        json={"review_status": review_status},
        headers=test_client._auth_headers,
    )
    assert response.status_code == 200
    return response.json()


class TestDayBookImport:
    """序时簿导入测试用例。"""

    def test_create_day_book_import_job(self, client):
        """测试创建序时簿导入任务。"""
        test_client, TestingSessionLocal = client
        ledger_id = _seed_ledger(TestingSessionLocal, test_client)

        response = test_client.post(
            "/api/import-jobs",
            json={
                "organization_name": "测试组织",
                "ledger_id": ledger_id,
                "source_type": "ledger_day_book",
            },
            headers=test_client._auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source_type"] == "ledger_day_book"
        assert data["status"] == "created"

    def test_upload_and_process_day_book(self, client):
        """测试完整的序时簿导入流程：上传文件 → 同步处理 → 验证结果。"""
        test_client, TestingSessionLocal = client
        ledger_id = _seed_ledger(TestingSessionLocal, test_client)
        _acknowledge_dimension_readiness(test_client, ledger_id)

        daybook_path = os.path.join(os.path.dirname(__file__), "../samples/daybook-sample.csv")
        assert os.path.exists(daybook_path), f"样例文件不存在: {daybook_path}"

        create_response = test_client.post(
            "/api/import-jobs",
            json={
                "organization_name": "测试组织",
                "ledger_id": ledger_id,
                "source_type": "ledger_day_book",
            },
            headers=test_client._auth_headers,
        )
        assert create_response.status_code == 200
        job_id = create_response.json()["id"]

        with open(daybook_path, "rb") as f:
            upload_response = test_client.post(
                f"/api/import-jobs/{job_id}/files",
                files={"file": ("daybook.csv", f, "text/csv")},
                headers=test_client._auth_headers,
            )
        assert upload_response.status_code == 200

        process_response = test_client.post(
            f"/api/import-jobs/{job_id}/process/sync",
            headers=test_client._auth_headers,
        )
        print("Process status:", process_response.status_code)
        if process_response.status_code != 200:
            print("Process error:", process_response.json())
        assert process_response.status_code == 200
        process_data = process_response.json()
        print("Process data:", process_data)
        assert process_data["report"]["total_entries"] == 6

    def test_day_book_report(self, client):
        """测试序时簿检测报告：验证跳号检测、借贷平衡、完整性评分。"""
        test_client, TestingSessionLocal = client
        ledger_id = _seed_ledger(TestingSessionLocal, test_client)
        _acknowledge_dimension_readiness(test_client, ledger_id)

        daybook_path = os.path.join(os.path.dirname(__file__), "../samples/daybook-sample.csv")

        create_response = test_client.post(
            "/api/import-jobs",
            json={
                "organization_name": "测试组织",
                "ledger_id": ledger_id,
                "source_type": "ledger_day_book",
            },
            headers=test_client._auth_headers,
        )
        job_id = create_response.json()["id"]

        with open(daybook_path, "rb") as f:
            test_client.post(
                f"/api/import-jobs/{job_id}/files",
                files={"file": ("daybook.csv", f, "text/csv")},
                headers=test_client._auth_headers,
            )

        test_client.post(
            f"/api/import-jobs/{job_id}/process/sync",
            headers=test_client._auth_headers,
        )

        report_response = test_client.get(
            f"/api/import-jobs/{job_id}/day-book-report",
            headers=test_client._auth_headers,
        )
        assert report_response.status_code == 200
        report_data = report_response.json()

        report = report_data
        assert report["total_vouchers"] == 3
        assert report["total_entries"] == 6
        assert report["skip_count"] == 0
        assert report["unbalanced_count"] == 0
        assert report["completeness_score"] == 100

    def test_period_suggestion(self, client):
        """测试期间推荐功能。"""
        test_client, TestingSessionLocal = client
        ledger_id = _seed_ledger(TestingSessionLocal, test_client)
        _acknowledge_dimension_readiness(test_client, ledger_id)

        daybook_path = os.path.join(os.path.dirname(__file__), "../samples/daybook-sample.csv")

        create_response = test_client.post(
            "/api/import-jobs",
            json={
                "organization_name": "测试组织",
                "ledger_id": ledger_id,
                "source_type": "ledger_day_book",
            },
            headers=test_client._auth_headers,
        )
        job_id = create_response.json()["id"]

        with open(daybook_path, "rb") as f:
            test_client.post(
                f"/api/import-jobs/{job_id}/files",
                files={"file": ("daybook.csv", f, "text/csv")},
                headers=test_client._auth_headers,
            )

        test_client.post(
            f"/api/import-jobs/{job_id}/process/sync",
            headers=test_client._auth_headers,
        )

        suggestion_response = test_client.get(
            f"/api/import-jobs/{job_id}/period-suggestion",
            headers=test_client._auth_headers,
        )
        assert suggestion_response.status_code == 200
        suggestion_data = suggestion_response.json()
        assert suggestion_data["detected_month"] == "2026-01"

    def test_import_entries_created(self, client):
        """验证导入后的分录数据正确性。"""
        test_client, TestingSessionLocal = client
        ledger_id = _seed_ledger(TestingSessionLocal, test_client)
        _acknowledge_dimension_readiness(test_client, ledger_id)

        daybook_path = os.path.join(os.path.dirname(__file__), "../samples/daybook-sample.csv")

        create_response = test_client.post(
            "/api/import-jobs",
            json={
                "organization_name": "测试组织",
                "ledger_id": ledger_id,
                "source_type": "ledger_day_book",
            },
            headers=test_client._auth_headers,
        )
        job_id = create_response.json()["id"]

        with open(daybook_path, "rb") as f:
            test_client.post(
                f"/api/import-jobs/{job_id}/files",
                files={"file": ("daybook.csv", f, "text/csv")},
                headers=test_client._auth_headers,
            )

        test_client.post(
            f"/api/import-jobs/{job_id}/process/sync",
            headers=test_client._auth_headers,
        )

        _review_all_staging(test_client, job_id)
        confirm_response = test_client.post(
            f"/api/import-jobs/{job_id}/confirm",
            headers=test_client._auth_headers,
        )
        assert confirm_response.status_code == 200

        db = TestingSessionLocal()
        try:
            entries = db.query(AccountingEntry).filter(
                AccountingEntry.import_job_id == job_id
            ).all()

            assert len(entries) == 6

            debit_total = sum(Decimal(str(e.debit_amount)) for e in entries)
            credit_total = sum(Decimal(str(e.credit_amount)) for e in entries)
            assert debit_total == credit_total == Decimal("75000")

            voucher_nos = sorted(set(e.voucher_no for e in entries))
            assert voucher_nos == ["记-001", "记-002", "记-003"]
        finally:
            db.close()

    def test_audit_day_book_import(self, client):
        """测试审计模式序时簿导入（audit_day_book）。"""
        from app.models.project import Project
        from app.models.project_ledger import ProjectLedger

        test_client, TestingSessionLocal = client
        ledger_id = _seed_ledger(TestingSessionLocal, test_client)
        _acknowledge_dimension_readiness(test_client, ledger_id)

        db = TestingSessionLocal()
        try:
            team = db.query(Team).filter(Team.name == "序时簿测试团队").first()
            project = Project(
                team_id=team.id,
                name="审计测试项目",
                type="audit",
                status="active",
            )
            db.add(project)
            db.flush()

            link = ProjectLedger(
                project_id=project.id,
                ledger_id=ledger_id,
            )
            db.add(link)
            db.commit()
            project_id = project.id
        finally:
            db.close()

        daybook_path = os.path.join(os.path.dirname(__file__), "../samples/daybook-sample.csv")

        create_response = test_client.post(
            "/api/import-jobs",
            json={
                "organization_name": "测试组织",
                "ledger_id": ledger_id,
                "project_id": project_id,
                "source_type": "audit_day_book",
            },
            headers=test_client._auth_headers,
        )
        assert create_response.status_code == 200
        job_id = create_response.json()["id"]

        with open(daybook_path, "rb") as f:
            test_client.post(
                f"/api/import-jobs/{job_id}/files",
                files={"file": ("daybook.csv", f, "text/csv")},
                headers=test_client._auth_headers,
            )

        process_response = test_client.post(
            f"/api/import-jobs/{job_id}/process/sync",
            headers=test_client._auth_headers,
        )
        assert process_response.status_code == 200
