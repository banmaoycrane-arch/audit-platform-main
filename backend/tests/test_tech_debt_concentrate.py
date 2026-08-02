# -*- coding: utf-8 -*-
"""集中技术负债回归：DocumentTag ledger_id + 凭证签章 API 暴露。"""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import Organization, SourceFile, Voucher
from app.db.session import Base, get_db
from app.main import app
from app.models.ledger import Ledger
from app.models.team import Team
from app.models.user import User
from app.services.doc_parsing.document_tag_service import (
    create_document_tag,
    resolve_document_ledger_id,
)


def test_resolve_document_ledger_id_from_source_file():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    org = Organization(name="org")
    db.add(org)
    db.flush()
    team = Team(name="t")
    db.add(team)
    db.flush()
    ledger = Ledger(name="L", team_id=team.id)
    db.add(ledger)
    db.flush()
    from app.db.models import ImportJob

    job = ImportJob(organization_id=org.id, ledger_id=ledger.id, status="completed")
    db.add(job)
    db.flush()
    sf = SourceFile(
        organization_id=org.id,
        import_job_id=job.id,
        ledger_id=ledger.id,
        filename="a.pdf",
        file_type="pdf",
        storage_path="/tmp/a.pdf",
    )
    db.add(sf)
    db.flush()

    assert resolve_document_ledger_id(db, sf.id) == ledger.id
    tag = create_document_tag(
        db,
        document_id=sf.id,
        document_type="invoice",
        tag="差旅",
        tag_type="business",
    )
    assert tag.ledger_id == ledger.id
    db.close()


def test_voucher_detail_exposes_signature_fields():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            reg = client.post(
                "/api/auth/register",
                json={
                    "username": "sig_user_td",
                    "password": "TestPass123!",
                    "agreed_terms": True,
                    "agreed_privacy": True,
                },
            )
            assert reg.status_code == 200
            token = reg.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            team = client.post(
                "/api/teams",
                headers=headers,
                json={"name": "签章团队", "type": "company"},
            )
            ledger = client.post(
                "/api/ledgers",
                headers=headers,
                json={"team_id": team.json()["id"], "name": "签章账簿"},
            )
            ledger_id = ledger.json()["id"]
            client.post(f"/api/ledgers/{ledger_id}/switch", headers=headers)
            period = client.post(
                "/api/accounting-periods",
                headers={**headers, "X-Ledger-Id": str(ledger_id)},
                json={
                    "ledger_id": ledger_id,
                    "period_code": "2026-01",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                },
            )
            assert period.status_code in (200, 201), period.text
            period_id = period.json()["id"]
            org_id = period.json().get("organization_id")
            create = client.post(
                "/api/vouchers",
                headers={**headers, "X-Ledger-Id": str(ledger_id)},
                json={
                    "ledger_id": ledger_id,
                    "organization_id": org_id,
                    "period_id": period_id,
                    "voucher_type": "记",
                    "voucher_number": "9001",
                    "voucher_date": "2026-01-10",
                    "summary": "签章暴露测试",
                    "lines": [
                        {
                            "line_no": 1,
                            "summary": "借",
                            "account_code": "1002",
                            "debit_amount": "100.00",
                            "credit_amount": "0.00",
                        },
                        {
                            "line_no": 2,
                            "summary": "贷",
                            "account_code": "6001",
                            "debit_amount": "0.00",
                            "credit_amount": "100.00",
                        },
                    ],
                },
            )
            assert create.status_code == 201, create.text
            voucher_id = create.json()["data"]["voucher_id"]

            # 直接写签章字段后读详情
            with next(override_get_db()) as db:
                user = db.query(User).filter(User.username == "sig_user_td").one()
                voucher = db.get(Voucher, voucher_id)
                voucher.source_preparer_name = "制单张三"
                voucher.cross_reviewed_by_user_id = user.id
                voucher.approved_by_user_id = user.id
                db.commit()

            detail = client.get(f"/api/vouchers/{voucher_id}", headers=headers)
            assert detail.status_code == 200, detail.text
            data = detail.json()["data"]
            assert data["source_preparer_name"] == "制单张三"
            assert data["cross_reviewed_by_user_id"] == data.get("cross_reviewed_by_user_id")
            assert data["cross_reviewed_by_name"]
            assert data["approved_by_name"]

            # TD-031：分录列表透出 voucher_id，供明细账等走主路径
            entries = client.get(
                f"/api/entries/chronological?ledger_id={ledger_id}&limit=20",
                headers={**headers, "X-Ledger-Id": str(ledger_id)},
            )
            assert entries.status_code == 200, entries.text
            entry_items = entries.json()["items"]
            assert entry_items
            assert any(item.get("voucher_id") == voucher_id for item in entry_items)
    finally:
        app.dependency_overrides.clear()
