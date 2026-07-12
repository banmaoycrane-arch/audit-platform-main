"""Staging LLM 待处理列表测试。"""

from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import ImportJob, Ledger, Organization, StagingAccountingEntry, Team
from app.db.session import Base
from app.services.doc_parsing.staging_llm_tag_resolution_service import StagingLlmTagResolutionService


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()


def test_list_pending_staging_rows(db):
    org = Organization(name="测试企业")
    db.add(org)
    db.flush()
    team = Team(name="团队")
    db.add(team)
    db.flush()
    ledger = Ledger(name="账簿", team_id=team.id)
    db.add(ledger)
    db.flush()
    job = ImportJob(organization_id=org.id, ledger_id=ledger.id, source_type="ledger_day_book", status="preview")
    db.add(job)
    db.flush()
    db.add(
        StagingAccountingEntry(
            import_job_id=job.id,
            organization_id=org.id,
            ledger_id=ledger.id,
            summary="支付货款",
            account_code="1122",
            resolved_account_code="1122",
            debit_amount=Decimal("1"),
            original_row={"_requires_llm_resolution": True},
        )
    )
    db.commit()

    service = StagingLlmTagResolutionService(db, ledger_id=ledger.id)
    pending = service.list_pending_rows(job.id)
    assert len(pending) == 1

    result = service.batch_resolve(job.id, dry_run=True)
    assert result.total_rows == 1
