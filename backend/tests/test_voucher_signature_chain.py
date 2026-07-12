"""凭证签章链：制单人解析、复核记名、审核确认。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import ImportJob, Organization, StagingAccountingEntry, Team, Voucher
from app.db.session import Base
from app.services.audit.structured_import_service import (
    batch_update_preview_review,
    confirm_structured_import,
)
from app.services.audit.voucher_signature_service import extract_source_preparer_name
from app.services.audit.staging_review_service import group_staging_rows


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_job(db) -> tuple[ImportJob, int]:
    org = Organization(name="签章测试")
    db.add(org)
    db.flush()
    team = Team(name="团队")
    db.add(team)
    db.flush()
    from app.db.models import Ledger

    ledger = Ledger(name="账簿", team_id=team.id)
    db.add(ledger)
    db.flush()
    job = ImportJob(
        organization_id=org.id,
        ledger_id=ledger.id,
        source_type="ledger_day_book",
        status="preview",
    )
    db.add(job)
    db.flush()
    for line_no in (1, 2):
        db.add(
            StagingAccountingEntry(
                import_job_id=job.id,
                organization_id=org.id,
                ledger_id=ledger.id,
                voucher_no="记-1",
                voucher_date=date(2024, 1, 5),
                entry_line_no=line_no,
                summary="测试",
                account_code="1001" if line_no == 1 else "6001",
                debit_amount=Decimal("100.00") if line_no == 1 else Decimal("0"),
                credit_amount=Decimal("0") if line_no == 1 else Decimal("100.00"),
                source_preparer_name="张三",
            )
        )
    db.commit()
    return job, ledger.id


def test_extract_source_preparer_from_original_row():
    name = extract_source_preparer_name(
        {"original_row": {"制单人": " 李四 "}, "summary": "x"}
    )
    assert name == "李四"


def test_review_stamps_cross_reviewer(db):
    job, _ledger_id = _seed_job(db)
    row = db.query(StagingAccountingEntry).first()
    batch_update_preview_review(db, job.id, [row.id], "verified", reviewed_by_user_id=42)
    db.expire_all()
    rows = db.query(StagingAccountingEntry).filter_by(import_job_id=job.id).all()
    assert all(r.cross_reviewed_by_user_id == 42 for r in rows)
    assert all(r.cross_reviewed_at is not None for r in rows)


def test_confirm_stamps_voucher_signatures(db):
    job, ledger_id = _seed_job(db)
    row = db.query(StagingAccountingEntry).first()
    batch_update_preview_review(db, job.id, [row.id], "verified", reviewed_by_user_id=42)
    result = confirm_structured_import(db, job, approved_by_user_id=99)
    assert result.success
    voucher = db.query(Voucher).filter_by(ledger_id=ledger_id, voucher_no="记-1").one()
    assert voucher.source_preparer_name == "张三"
    assert voucher.cross_reviewed_by_user_id == 42
    assert voucher.approved_by_user_id == 99
    assert voucher.approved_at is not None
