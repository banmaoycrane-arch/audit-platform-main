"""导入任务清理服务测试。"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import ImportJob, SourceFile, StagingAccountingEntry
from app.db.session import Base
from app.services.audit.import_job_cleanup_service import (
    bulk_purge_import_jobs,
    get_import_job_cleanup_summary,
    purge_import_job,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _add_failed_job(db_session, *, job_id_suffix: str = "1") -> ImportJob:
    job = ImportJob(
        organization_id=1,
        status="failed",
        source_type="ledger_day_book",
        error_message="解析超时",
    )
    db_session.add(job)
    db_session.flush()
    db_session.add(
        StagingAccountingEntry(
            import_job_id=job.id,
            organization_id=1,
            voucher_no=f"V-{job_id_suffix}",
            debit_amount=Decimal("1"),
            credit_amount=Decimal("0"),
            entry_line_no=1,
        )
    )
    db_session.add(
        SourceFile(
            organization_id=1,
            import_job_id=job.id,
            filename="test.csv",
            file_type="csv",
            storage_path=f"/tmp/nonexistent-{job.id}.csv",
        )
    )
    db_session.commit()
    return job


def test_cleanup_summary_marks_stuck_and_cleanable(db_session):
    failed = _add_failed_job(db_session, job_id_suffix="fail")
    stuck = ImportJob(
        organization_id=1,
        status="processing",
        source_type="ledger_day_book",
        created_at=datetime.now(timezone.utc) - timedelta(hours=3),
    )
    completed = ImportJob(
        organization_id=1,
        status="completed",
        source_type="ledger_day_book",
    )
    db_session.add_all([stuck, completed])
    db_session.commit()

    summary = get_import_job_cleanup_summary(db_session)
    by_id = {row["id"]: row for row in summary["jobs"]}

    assert summary["cleanable_count"] >= 2
    assert summary["stuck_count"] >= 2
    assert by_id[failed.id]["cleanable"] is True
    assert by_id[stuck.id]["stuck"] is True
    assert by_id[completed.id]["cleanable"] is False


def test_purge_import_job_removes_staging_and_record(db_session):
    job = _add_failed_job(db_session)
    job_id = job.id

    result = purge_import_job(db_session, job_id, delete_files=False)
    assert result["purged"] is True
    assert result["staging_rows_deleted"] >= 1
    assert db_session.get(ImportJob, job_id) is None
    assert (
        db_session.query(StagingAccountingEntry)
        .filter(StagingAccountingEntry.import_job_id == job_id)
        .count()
        == 0
    )


def test_bulk_purge_respects_keep_list(db_session):
    keep_job = _add_failed_job(db_session, job_id_suffix="keep")
    drop_job = _add_failed_job(db_session, job_id_suffix="drop")

    result = bulk_purge_import_jobs(
        db_session,
        stuck_only=True,
        keep_job_ids=[keep_job.id],
        delete_files=False,
    )

    assert result["purged_count"] >= 1
    assert db_session.get(ImportJob, keep_job.id) is not None
    assert db_session.get(ImportJob, drop_job.id) is None
    assert any(item["job_id"] == keep_job.id for item in result["skipped"])
