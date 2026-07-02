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
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import AccountingPeriod, Organization, AccountingEntry
from app.db.session import Base, engine
from app.main import app
from app.models.user import User
from app.models.ledger import Ledger
from app.models.user_ledger_auth import UserLedgerAuth
from app.models.team import Team
from app.core.security import create_access_token


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
        username="daybook_test_user",
        phone="13800000001",
        email="daybook_test@example.com",
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
    team = Team(name="序时簿测试团队", type="enterprise")
    db_session.add(team)
    db_session.commit()
    db_session.refresh(team)
    return team


@pytest.fixture
def test_organization(db_session):
    """创建测试组织。"""
    org = Organization(name="序时簿测试企业")
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture
def test_ledger(db_session, test_team, test_user, test_organization):
    """创建测试账簿并授权用户。"""
    from app.services.coa_service import init_default_accounts

    ledger = Ledger(
        team_id=test_team.id,
        name="序时簿测试账簿",
        status="active",
        accounting_start_date=date(2026, 1, 1),
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
    db_session.commit()
    return ledger


@pytest.fixture
def test_period(db_session, test_ledger, test_organization):
    """创建开放会计期间。"""
    period = AccountingPeriod(
        organization_id=test_organization.id,
        ledger_id=test_ledger.id,
        period_code="2026-01",
        period_type="monthly",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        status="open",
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


class TestDayBookImport:
    """序时簿导入测试用例。"""

    def test_create_day_book_import_job(self, db_session, test_ledger, test_organization, auth_headers):
        """测试创建序时簿导入任务。"""
        response = client.post(
            "/api/import-jobs",
            json={
                "organization_name": "测试组织",
                "ledger_id": test_ledger.id,
                "source_type": "ledger_day_book",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["source_type"] == "ledger_day_book"
        assert data["status"] == "created"

    def test_upload_and_process_day_book(self, db_session, test_ledger, test_organization, test_period, auth_headers):
        """测试完整的序时簿导入流程：上传文件 → 同步处理 → 验证结果。"""
        daybook_path = os.path.join(os.path.dirname(__file__), "../samples/daybook-sample.csv")
        assert os.path.exists(daybook_path), f"样例文件不存在: {daybook_path}"

        create_response = client.post(
            "/api/import-jobs",
            json={
                "organization_id": test_organization.id,
                "ledger_id": test_ledger.id,
                "source_type": "ledger_day_book",
            },
            headers=auth_headers,
        )
        assert create_response.status_code == 200
        job_id = create_response.json()["id"]

        with open(daybook_path, "rb") as f:
            upload_response = client.post(
                f"/api/import-jobs/{job_id}/files",
                files={"file": ("daybook.csv", f, "text/csv")},
                headers=auth_headers,
            )
        assert upload_response.status_code == 200

        process_response = client.post(
            f"/api/import-jobs/{job_id}/process/sync",
            headers=auth_headers,
        )
        print("Process status:", process_response.status_code)
        if process_response.status_code != 200:
            print("Process error:", process_response.json())
        assert process_response.status_code == 200
        process_data = process_response.json()
        print("Process data:", process_data)
        assert process_data["report"]["total_entries"] == 6

    def test_day_book_report(self, db_session, test_ledger, test_organization, test_period, auth_headers):
        """测试序时簿检测报告：验证跳号检测、借贷平衡、完整性评分。"""
        daybook_path = os.path.join(os.path.dirname(__file__), "../samples/daybook-sample.csv")

        create_response = client.post(
            "/api/import-jobs",
            json={
                "organization_name": "测试组织",
                "ledger_id": test_ledger.id,
                "source_type": "ledger_day_book",
            },
            headers=auth_headers,
        )
        job_id = create_response.json()["id"]

        with open(daybook_path, "rb") as f:
            client.post(
                f"/api/import-jobs/{job_id}/files",
                files={"file": ("daybook.csv", f, "text/csv")},
                headers=auth_headers,
            )

        client.post(
            f"/api/import-jobs/{job_id}/process/sync",
            headers=auth_headers,
        )

        report_response = client.get(
            f"/api/import-jobs/{job_id}/day-book-report",
            headers=auth_headers,
        )
        assert report_response.status_code == 200
        report_data = report_response.json()

        report = report_data
        assert report["total_vouchers"] == 3
        assert report["total_entries"] == 6
        assert report["skip_count"] == 0
        assert report["unbalanced_count"] == 0
        assert report["completeness_score"] == 100

    def test_period_suggestion(self, db_session, test_ledger, test_organization, test_period, auth_headers):
        """测试期间推荐功能。"""
        daybook_path = os.path.join(os.path.dirname(__file__), "../samples/daybook-sample.csv")

        create_response = client.post(
            "/api/import-jobs",
            json={
                "organization_name": "测试组织",
                "ledger_id": test_ledger.id,
                "source_type": "ledger_day_book",
            },
            headers=auth_headers,
        )
        job_id = create_response.json()["id"]

        with open(daybook_path, "rb") as f:
            client.post(
                f"/api/import-jobs/{job_id}/files",
                files={"file": ("daybook.csv", f, "text/csv")},
                headers=auth_headers,
            )

        client.post(
            f"/api/import-jobs/{job_id}/process/sync",
            headers=auth_headers,
        )

        suggestion_response = client.get(
            f"/api/import-jobs/{job_id}/period-suggestion",
            headers=auth_headers,
        )
        assert suggestion_response.status_code == 200
        suggestion_data = suggestion_response.json()
        assert suggestion_data["detected_month"] == "2026-01"

    def test_import_entries_created(self, db_session, test_ledger, test_organization, test_period, auth_headers):
        """验证导入后的分录数据正确性。"""
        daybook_path = os.path.join(os.path.dirname(__file__), "../samples/daybook-sample.csv")

        create_response = client.post(
            "/api/import-jobs",
            json={
                "organization_name": "测试组织",
                "ledger_id": test_ledger.id,
                "source_type": "ledger_day_book",
            },
            headers=auth_headers,
        )
        job_id = create_response.json()["id"]

        with open(daybook_path, "rb") as f:
            client.post(
                f"/api/import-jobs/{job_id}/files",
                files={"file": ("daybook.csv", f, "text/csv")},
                headers=auth_headers,
            )

        client.post(
            f"/api/import-jobs/{job_id}/process/sync",
            headers=auth_headers,
        )

        entries = db_session.query(AccountingEntry).filter(
            AccountingEntry.import_job_id == job_id
        ).all()

        assert len(entries) == 6

        debit_total = sum(Decimal(str(e.debit_amount)) for e in entries)
        credit_total = sum(Decimal(str(e.credit_amount)) for e in entries)
        assert debit_total == credit_total == Decimal("18000")

        voucher_nos = sorted(set(e.voucher_no for e in entries))
        assert voucher_nos == ["记-001", "记-002", "记-003"]

    def test_audit_day_book_import(self, db_session, test_ledger, test_organization, test_period, auth_headers):
        """测试审计模式序时簿导入（audit_day_book）。"""
        from app.models.project import Project
        from app.models.project_ledger import ProjectLedger

        project = Project(
            team_id=test_ledger.team_id,
            name="审计测试项目",
            type="audit",
            status="active",
        )
        db_session.add(project)
        db_session.flush()

        link = ProjectLedger(
            project_id=project.id,
            ledger_id=test_ledger.id,
        )
        db_session.add(link)
        db_session.commit()

        daybook_path = os.path.join(os.path.dirname(__file__), "../samples/daybook-sample.csv")

        create_response = client.post(
            "/api/import-jobs",
            json={
                "organization_name": "测试组织",
                "ledger_id": test_ledger.id,
                "project_id": project.id,
                "source_type": "audit_day_book",
            },
            headers=auth_headers,
        )
        assert create_response.status_code == 200
        job_id = create_response.json()["id"]

        with open(daybook_path, "rb") as f:
            client.post(
                f"/api/import-jobs/{job_id}/files",
                files={"file": ("daybook.csv", f, "text/csv")},
                headers=auth_headers,
            )

        process_response = client.post(
            f"/api/import-jobs/{job_id}/process/sync",
            headers=auth_headers,
        )
        assert process_response.status_code == 200