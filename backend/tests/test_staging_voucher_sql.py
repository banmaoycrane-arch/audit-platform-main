"""Staging 凭证 SQL 分组分页测试。"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import ImportJob, StagingAccountingEntry
from app.db.session import Base
from app.services.audit.staging_voucher_query_service import (
    compute_review_stats_sql,
    paginate_preview_vouchers_sql,
)
from app.services.audit.structured_import_service import list_preview_vouchers


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


def _seed_job_with_vouchers(db_session) -> int:
    from app.models.team import Team
    from app.models.ledger import Ledger

    team = Team(name="SQL分页测试团队")
    db_session.add(team)
    db_session.flush()
    ledger = Ledger(name="SQL分页测试账簿", team_id=team.id)
    db_session.add(ledger)
    db_session.flush()
    job = ImportJob(
        organization_id=1,
        ledger_id=ledger.id,
        status="preview",
        source_type="ledger_day_book",
    )
    db_session.add(job)
    db_session.flush()

    rows = [
        StagingAccountingEntry(
            import_job_id=job.id,
            organization_id=1,
            ledger_id=ledger.id,
            voucher_no="记-001",
            voucher_date=date(2026, 1, 3),
            summary="办公费",
            account_name="管理费用",
            debit_amount=Decimal("100"),
            credit_amount=Decimal("0"),
            entry_line_no=1,
            review_status="draft",
        ),
        StagingAccountingEntry(
            import_job_id=job.id,
            organization_id=1,
            ledger_id=ledger.id,
            voucher_no="记-001",
            voucher_date=date(2026, 1, 3),
            summary="银行存款",
            account_name="银行存款",
            debit_amount=Decimal("0"),
            credit_amount=Decimal("100"),
            entry_line_no=2,
            review_status="draft",
        ),
        StagingAccountingEntry(
            import_job_id=job.id,
            organization_id=1,
            ledger_id=ledger.id,
            voucher_no="记-002",
            voucher_date=date(2026, 2, 4),
            summary="收入",
            account_name="主营业务收入",
            debit_amount=Decimal("0"),
            credit_amount=Decimal("200"),
            entry_line_no=1,
            review_status="verified",
        ),
        StagingAccountingEntry(
            import_job_id=job.id,
            organization_id=1,
            ledger_id=ledger.id,
            voucher_no="记-002",
            voucher_date=date(2026, 2, 4),
            summary="银行存款",
            account_name="银行存款",
            debit_amount=Decimal("200"),
            credit_amount=Decimal("0"),
            entry_line_no=2,
            review_status="verified",
        ),
        StagingAccountingEntry(
            import_job_id=job.id,
            organization_id=1,
            ledger_id=ledger.id,
            voucher_no=None,
            voucher_date=None,
            summary="无凭证号行",
            account_name="库存现金",
            debit_amount=Decimal("10"),
            credit_amount=Decimal("10"),
            entry_line_no=1,
            review_status="draft",
        ),
    ]
    db_session.add_all(rows)
    db_session.commit()
    return job.id


def test_sqlite_balanced_large_voucher_not_false_unbalanced(db_session):
    """SQLite 对 SUM 列用 != 比较可能误报，修复后应识别为平衡。"""
    from app.models.team import Team
    from app.models.ledger import Ledger

    team = Team(name="平衡误报测试")
    db_session.add(team)
    db_session.flush()
    ledger = Ledger(name="平衡误报账簿", team_id=team.id)
    db_session.add(ledger)
    db_session.flush()
    job = ImportJob(
        organization_id=1,
        ledger_id=ledger.id,
        status="preview",
        source_type="ledger_day_book",
    )
    db_session.add(job)
    db_session.flush()

    db_session.add_all(
        [
            StagingAccountingEntry(
                import_job_id=job.id,
                organization_id=1,
                ledger_id=ledger.id,
                voucher_no="记-0004",
                voucher_date=date(2025, 8, 22),
                summary="借方1",
                account_name="应收账款",
                debit_amount=Decimal("561311.83"),
                credit_amount=Decimal("0"),
                entry_line_no=1,
                review_status="draft",
            ),
            StagingAccountingEntry(
                import_job_id=job.id,
                organization_id=1,
                ledger_id=ledger.id,
                voucher_no="记-0004",
                voucher_date=date(2025, 8, 22),
                summary="借方2",
                account_name="应收账款",
                debit_amount=Decimal("561311.83"),
                credit_amount=Decimal("0"),
                entry_line_no=2,
                review_status="draft",
            ),
            StagingAccountingEntry(
                import_job_id=job.id,
                organization_id=1,
                ledger_id=ledger.id,
                voucher_no="记-0004",
                voucher_date=date(2025, 8, 22),
                summary="贷方",
                account_name="银行存款",
                debit_amount=Decimal("0"),
                credit_amount=Decimal("1122623.66"),
                entry_line_no=3,
                review_status="draft",
            ),
        ]
    )
    db_session.commit()

    stats = compute_review_stats_sql(db_session, job.id)
    assert stats["unbalanced_voucher_nos"] == []

    items, total = paginate_preview_vouchers_sql(
        db_session, job.id, review_filter="unbalanced", limit=10, offset=0
    )
    assert total == 0
    assert items == []


def test_compute_review_stats_sql(db_session):
    job_id = _seed_job_with_vouchers(db_session)
    stats = compute_review_stats_sql(db_session, job_id)
    assert stats["total_vouchers"] == 3
    assert stats["verified_vouchers"] == 1
    assert stats["partial_vouchers"] == 0
    assert stats["total_lines"] == 5
    assert stats["unbalanced_voucher_nos"] == []


def test_paginate_preview_vouchers_sql_filters(db_session):
    job_id = _seed_job_with_vouchers(db_session)

    pending, pending_total = paginate_preview_vouchers_sql(
        db_session, job_id, review_filter="pending", limit=10, offset=0
    )
    assert pending_total == 2
    assert {item["voucher_no"] for item in pending if item["voucher_no"]} == {"记-001"}

    verified, verified_total = paginate_preview_vouchers_sql(
        db_session, job_id, review_filter="verified", limit=10, offset=0
    )
    assert verified_total == 1
    assert verified[0]["voucher_no"] == "记-002"

    page, total = paginate_preview_vouchers_sql(
        db_session, job_id, review_filter="all", limit=1, offset=1
    )
    assert total == 3
    assert len(page) == 1


def test_paginate_preview_vouchers_sql_search(db_session):
    job_id = _seed_job_with_vouchers(db_session)
    items, total = paginate_preview_vouchers_sql(
        db_session, job_id, review_filter="all", search="办公", limit=10, offset=0
    )
    assert total == 1
    assert items[0]["voucher_no"] == "记-001"


def test_list_preview_vouchers_service_uses_sql(db_session):
    job_id = _seed_job_with_vouchers(db_session)
    items, total, stats = list_preview_vouchers(
        db_session, job_id, review_filter="pending", limit=20, offset=0
    )
    assert total == 2
    assert stats["total_vouchers"] == 3
    assert len(items) == 2
    assert all(item["group_key"] for item in items)
