"""审计快照导入与合规审查单测。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    ImportJob,
    Organization,
    Project,
    StagingAccountingEntry,
    StagingAccountBalance,
    Team,
)
from app.db.session import Base
from app.services.audit.compliance_review_service import review_staging_compliance
from app.services.audit.structured_import_service import confirm_structured_import, preview_structured_import
from app.services.doc_parsing.structured_snapshot_parser import parse_account_balance_rows


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
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def balance_csv(tmp_path: Path) -> str:
    path = tmp_path / "balance.csv"
    path.write_text(
        "科目代码,科目名称,期初余额,借方,贷方,期末余额\n"
        "1001,库存现金,1000.00,500.00,200.00,1300.00\n"
        "1002,银行存款,50000.00,0,0,50000.00\n",
        encoding="utf-8",
    )
    return str(path)


def test_parse_account_balance_rows(balance_csv: str):
    rows = parse_account_balance_rows(balance_csv)
    assert len(rows) == 2
    assert rows[0]["account_code"] == "1001"
    assert rows[0]["closing_balance"] == Decimal("1300.00")


def test_compliance_review_flags_unbalanced(db):
    org = Organization(name="测试组织")
    db.add(org)
    db.flush()
    job = ImportJob(organization_id=org.id, source_type="ledger_day_book", status="preview")
    db.add(job)
    db.flush()
    db.add(
        StagingAccountingEntry(
            import_job_id=job.id,
            organization_id=org.id,
            voucher_no="记-001",
            voucher_date=date(2024, 1, 1),
            summary="测试",
            account_code="1001",
            account_name="库存现金",
            debit_amount=Decimal("100.00"),
            credit_amount=Decimal("0.00"),
            review_status="draft",
        )
    )
    db.add(
        StagingAccountingEntry(
            import_job_id=job.id,
            organization_id=org.id,
            voucher_no="记-001",
            voucher_date=date(2024, 1, 1),
            summary="测试",
            account_code="2001",
            account_name="应付账款",
            debit_amount=Decimal("0.00"),
            credit_amount=Decimal("50.00"),
            review_status="draft",
        )
    )
    db.commit()

    result = review_staging_compliance(db, job.id, mode="each")
    assert result["reviewed_vouchers"] == 1
    rows = db.query(StagingAccountingEntry).filter(StagingAccountingEntry.import_job_id == job.id).all()
    assert all(row.compliance_severity == "error" for row in rows)


def test_snapshot_preview_and_confirm(db, balance_csv: str):
    team = Team(name="审计团队")
    db.add(team)
    db.flush()
    org = Organization(name="被审单位")
    db.add(org)
    db.flush()
    project = Project(name="2024年审计", team_id=team.id)
    db.add(project)
    db.flush()
    job = ImportJob(
        organization_id=org.id,
        project_id=project.id,
        source_type="audit_balance_sheet",
        status="created",
    )
    db.add(job)
    db.flush()

    from app.db.models import SourceFile

    db.add(
        SourceFile(
            organization_id=org.id,
            import_job_id=job.id,
            filename="balance.csv",
            file_type="csv",
            storage_path=balance_csv,
        )
    )
    db.commit()

    preview = preview_structured_import(db, job)
    assert preview.success is True
    assert preview.entries_created == 2
    staging_count = db.query(StagingAccountBalance).filter(StagingAccountBalance.import_job_id == job.id).count()
    assert staging_count == 2

    confirm = confirm_structured_import(db, job)
    assert confirm.success is True
    assert confirm.entries_created == 2
    assert db.query(StagingAccountBalance).filter(StagingAccountBalance.import_job_id == job.id).count() == 0
