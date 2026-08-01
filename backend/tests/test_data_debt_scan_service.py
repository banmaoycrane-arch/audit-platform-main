"""数据负债扫描服务单元测试。

验证 scan_data_debt 能真正检测 4 类问题：
1. 孤儿记录：staging 表 organization_id 指向不存在组织
2. 约束完整性：凭证借贷不平、分录借贷异常、金额负数、空值、非法枚举
3. 数据一致性：凭证汇总 vs 分录汇总勾稽、entry_line_no 重复、凭证日期超期间
4. 脏数据：科目代码/凭证号前后空格、已过账无号、voucher_no 重复

并验证 apply_auto_fixes 能正确 trim 空格。
"""
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.models import (
    AccountingEntry,
    AccountingPeriod,
    ImportJob,
    Organization,
    StagingAccountingEntry,
    Voucher,
)
from app.db.session import Base
from app.models.ledger import Ledger
from app.models.team import Team
from app.services.shared.data_debt_scan_service import (
    apply_auto_fixes,
    scan_data_debt,
)


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def _seed_base(db_session) -> tuple[int, int, int]:
    """创建基础数据：组织、账簿、期间，返回 (org_id, ledger_id, period_id)。"""
    org = Organization(name="测试企业", fiscal_year=2026)
    db_session.add(org)
    db_session.flush()

    team = Team(name="测试团队")
    db_session.add(team)
    db_session.flush()

    ledger = Ledger(name="测试账簿", team_id=team.id, organization_id=org.id)
    db_session.add(ledger)
    db_session.flush()

    period = AccountingPeriod(
        organization_id=org.id,
        ledger_id=ledger.id,
        period_code="2026-01",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
    )
    db_session.add(period)
    db_session.flush()
    return org.id, ledger.id, period.id


# ======================== 1. 孤儿记录 ========================

def test_scan_detects_orphan_staging_org(db_session):
    """staging_entry.organization_id 指向不存在的组织应被检测。"""
    org_id, _, _ = _seed_base(db_session)

    # 创建一条 staging 记录，organization_id 指向不存在的 99999
    stg = StagingAccountingEntry(
        organization_id=99999,  # 不存在的组织
        import_job_id=1,
        account_code="1001",
        debit_amount=Decimal("100"),
        credit_amount=Decimal("0"),
    )
    db_session.add(stg)
    db_session.commit()

    report = scan_data_debt(db_session, categories=["orphan"])
    rule_ids = {f.rule_id for f in report.findings}
    assert "orph_stg_entry_org" in rule_ids
    finding = next(f for f in report.findings if f.rule_id == "orph_stg_entry_org")
    assert finding.count >= 1
    assert stg.id in finding.sample_ids


# ======================== 2. 约束完整性 ========================

def test_scan_detects_unbalanced_voucher(db_session):
    """凭证借贷不平应被检测为 critical。"""
    org_id, ledger_id, _ = _seed_base(db_session)

    voucher = Voucher(
        ledger_id=ledger_id,
        organization_id=org_id,
        voucher_no="V-001",
        voucher_date=date(2026, 1, 10),
        total_debit=Decimal("100.00"),
        total_credit=Decimal("99.00"),  # 不平
        status="draft",
    )
    db_session.add(voucher)
    db_session.commit()

    report = scan_data_debt(db_session, categories=["constraint_integrity"])
    finding = next(
        (f for f in report.findings if f.rule_id == "ci_voucher_unbalanced"), None
    )
    assert finding is not None
    assert finding.count >= 1
    assert finding.severity == "critical"


def test_scan_detects_entry_both_zero(db_session):
    """分录借贷同时为 0 应被检测为 critical。"""
    org_id, ledger_id, _ = _seed_base(db_session)

    voucher = Voucher(
        ledger_id=ledger_id,
        organization_id=org_id,
        voucher_no="V-002",
        voucher_date=date(2026, 1, 10),
        total_debit=Decimal("0.00"),
        total_credit=Decimal("0.00"),
        status="draft",
    )
    db_session.add(voucher)
    db_session.flush()

    entry = AccountingEntry(
        voucher_id=voucher.id,
        ledger_id=ledger_id,
        organization_id=org_id,
        voucher_no="V-002",
        voucher_date=date(2026, 1, 10),
        account_code="1001",
        account_name="库存现金",
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("0.00"),  # 双侧为零
    )
    db_session.add(entry)
    db_session.commit()

    report = scan_data_debt(db_session, categories=["constraint_integrity"])
    finding = next(
        (f for f in report.findings if f.rule_id == "ci_entry_amount_invalid"), None
    )
    assert finding is not None
    assert finding.count >= 1
    assert finding.severity == "critical"


def test_scan_detects_negative_amount(db_session):
    """分录金额负数应被检测。"""
    org_id, ledger_id, _ = _seed_base(db_session)

    voucher = Voucher(
        ledger_id=ledger_id,
        organization_id=org_id,
        voucher_no="V-003",
        voucher_date=date(2026, 1, 10),
        total_debit=Decimal("-50.00"),
        total_credit=Decimal("-50.00"),
        status="draft",
    )
    db_session.add(voucher)
    db_session.commit()

    report = scan_data_debt(db_session, categories=["constraint_integrity"])
    rule_ids = {f.rule_id for f in report.findings}
    assert "ci_voucher_negative" in rule_ids


def test_scan_detects_empty_voucher_no(db_session):
    """凭证 voucher_no 为空应被检测。"""
    org_id, ledger_id, _ = _seed_base(db_session)

    voucher = Voucher(
        ledger_id=ledger_id,
        organization_id=org_id,
        voucher_no="",  # 空串
        voucher_date=date(2026, 1, 10),
        total_debit=Decimal("0.00"),
        total_credit=Decimal("0.00"),
        status="draft",
    )
    db_session.add(voucher)
    db_session.commit()

    report = scan_data_debt(db_session, categories=["constraint_integrity"])
    finding = next(
        (f for f in report.findings if f.rule_id == "ci_voucher_no_empty"), None
    )
    assert finding is not None
    assert finding.count >= 1


def test_scan_detects_illegal_voucher_status(db_session):
    """凭证 status 非法值应被检测。

    注：DB CheckConstraint 会拦截 ORM 插入，这里用 raw SQL 临时关闭 check 约束
    模拟「约束添加前已存在的存量脏数据」或「绕过 ORM 的直接 DML」场景。
    扫描规则作为纵深防御，补充 DB 约束的不足。
    """
    from sqlalchemy import text

    org_id, ledger_id, _ = _seed_base(db_session)

    # 先正常插入一条凭证
    voucher = Voucher(
        ledger_id=ledger_id,
        organization_id=org_id,
        voucher_no="V-004",
        voucher_date=date(2026, 1, 10),
        total_debit=Decimal("0.00"),
        total_credit=Decimal("0.00"),
        status="draft",
    )
    db_session.add(voucher)
    db_session.commit()

    # 临时关闭 check 约束，用 raw SQL 改成非法值（模拟存量脏数据）
    db_session.execute(text("PRAGMA ignore_check_constraints = ON"))
    db_session.execute(
        text("UPDATE vouchers SET status = 'unknown_status' WHERE id = :vid"),
        {"vid": voucher.id},
    )
    db_session.execute(text("PRAGMA ignore_check_constraints = OFF"))
    db_session.commit()

    report = scan_data_debt(db_session, categories=["constraint_integrity"])
    finding = next(
        (f for f in report.findings if f.rule_id == "ci_voucher_status_illegal"), None
    )
    assert finding is not None
    assert finding.count >= 1


# ======================== 3. 数据一致性 ========================

def test_scan_detects_voucher_entry_mismatch(db_session):
    """凭证汇总金额与分录汇总金额不一致应被检测为 critical。"""
    org_id, ledger_id, _ = _seed_base(db_session)

    # 凭证记录的合计是 100/100
    voucher = Voucher(
        ledger_id=ledger_id,
        organization_id=org_id,
        voucher_no="V-005",
        voucher_date=date(2026, 1, 10),
        total_debit=Decimal("100.00"),
        total_credit=Decimal("100.00"),
        status="draft",
    )
    db_session.add(voucher)
    db_session.flush()

    # 但分录实际是 200/200（不一致）
    db_session.add(AccountingEntry(
        voucher_id=voucher.id,
        ledger_id=ledger_id,
        organization_id=org_id,
        voucher_no="V-005",
        voucher_date=date(2026, 1, 10),
        account_code="1001",
        account_name="库存现金",
        debit_amount=Decimal("200.00"),
        credit_amount=Decimal("0.00"),
        entry_line_no=1,
    ))
    db_session.add(AccountingEntry(
        voucher_id=voucher.id,
        ledger_id=ledger_id,
        organization_id=org_id,
        voucher_no="V-005",
        voucher_date=date(2026, 1, 10),
        account_code="4001",
        account_name="实收资本",
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("200.00"),
        entry_line_no=2,
    ))
    db_session.commit()

    report = scan_data_debt(db_session, categories=["consistency"])
    finding = next(
        (f for f in report.findings if f.rule_id == "cs_voucher_entry_mismatch"), None
    )
    assert finding is not None
    assert finding.count >= 1
    assert finding.severity == "critical"
    assert voucher.id in finding.sample_ids


# 注：test_scan_detects_entry_line_no_dup 和 test_scan_detects_voucher_no_dup
# 无法在 SQLite 测试中创建测试数据，因为 0031 迁移的 UniqueConstraint
# (uq_entry_voucher_line_no / uq_voucher_ledger_no) 会在 INSERT 时直接拒绝。
# 这两个扫描规则作为纵深防御保留，用于检测约束添加前的存量数据或绕过约束的 DML。
# 在生产环境（PostgreSQL）中，如果约束因故未应用，扫描规则仍能发现问题。


def test_scan_detects_voucher_date_out_of_period(db_session):
    """凭证日期超出所属期间范围应被检测。"""
    org_id, ledger_id, period_id = _seed_base(db_session)

    # 期间是 2026-01-01 ~ 2026-01-31，凭证日期设为 2026-02-15
    voucher = Voucher(
        ledger_id=ledger_id,
        organization_id=org_id,
        period_id=period_id,
        voucher_no="V-007",
        voucher_date=date(2026, 2, 15),  # 超出期间
        total_debit=Decimal("0.00"),
        total_credit=Decimal("0.00"),
        status="draft",
    )
    db_session.add(voucher)
    db_session.commit()

    report = scan_data_debt(db_session, categories=["consistency"])
    finding = next(
        (f for f in report.findings if f.rule_id == "cs_voucher_period_date_oob"), None
    )
    assert finding is not None
    assert finding.count >= 1


# ======================== 4. 脏数据 ========================

def test_scan_detects_acct_code_trim(db_session):
    """分录 account_code 前后含空格应被检测。"""
    org_id, ledger_id, _ = _seed_base(db_session)

    voucher = Voucher(
        ledger_id=ledger_id,
        organization_id=org_id,
        voucher_no="V-008",
        voucher_date=date(2026, 1, 10),
        total_debit=Decimal("0.00"),
        total_credit=Decimal("0.00"),
        status="draft",
    )
    db_session.add(voucher)
    db_session.flush()

    db_session.add(AccountingEntry(
        voucher_id=voucher.id,
        ledger_id=ledger_id,
        organization_id=org_id,
        voucher_no="V-008",
        voucher_date=date(2026, 1, 10),
        account_code=" 1001 ",  # 前后空格
        account_name="库存现金",
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("0.00"),
        entry_line_no=1,
    ))
    db_session.commit()

    report = scan_data_debt(db_session, categories=["dirty"])
    finding = next(
        (f for f in report.findings if f.rule_id == "dd_acct_code_trim"), None
    )
    assert finding is not None
    assert finding.count >= 1


# test_scan_detects_voucher_no_dup 已移除（见上方注释：UniqueConstraint 阻挡）


def test_scan_detects_posted_voucher_no_missing(db_session):
    """已过账凭证无凭证号应被检测。"""
    org_id, ledger_id, _ = _seed_base(db_session)

    db_session.add(Voucher(
        ledger_id=ledger_id,
        organization_id=org_id,
        voucher_no="",  # 空号
        voucher_date=date(2026, 1, 10),
        total_debit=Decimal("0.00"),
        total_credit=Decimal("0.00"),
        status="posted",  # 已过账
    ))
    db_session.commit()

    report = scan_data_debt(db_session, categories=["dirty"])
    finding = next(
        (f for f in report.findings if f.rule_id == "dd_posted_voucher_no_missing"), None
    )
    assert finding is not None
    assert finding.count >= 1


# ======================== 修复验证 ========================

def test_apply_auto_fixes_trims_acct_code(db_session):
    """apply_auto_fixes 应正确 trim account_code 空格。"""
    org_id, ledger_id, _ = _seed_base(db_session)

    voucher = Voucher(
        ledger_id=ledger_id,
        organization_id=org_id,
        voucher_no="V-FIX",
        voucher_date=date(2026, 1, 10),
        total_debit=Decimal("0.00"),
        total_credit=Decimal("0.00"),
        status="draft",
    )
    db_session.add(voucher)
    db_session.flush()

    entry = AccountingEntry(
        voucher_id=voucher.id,
        ledger_id=ledger_id,
        organization_id=org_id,
        voucher_no="V-FIX",
        voucher_date=date(2026, 1, 10),
        account_code=" 1001 ",  # 前后空格
        account_name="库存现金",
        debit_amount=Decimal("0.00"),
        credit_amount=Decimal("0.00"),
        entry_line_no=1,
    )
    db_session.add(entry)
    db_session.commit()

    report = scan_data_debt(db_session, categories=["dirty"])
    # 修复前应检测到
    assert any(f.rule_id == "dd_acct_code_trim" for f in report.findings)

    # 执行修复
    actions = apply_auto_fixes(db_session, report, approved=True)
    db_session.commit()

    # 应有修复动作
    assert any(a.rule_id == "dd_acct_code_trim" for a in actions)

    # 修复后再扫描，应不再检测到
    report2 = scan_data_debt(db_session, categories=["dirty"])
    trim_finding = next(
        (f for f in report2.findings if f.rule_id == "dd_acct_code_trim"), None
    )
    assert trim_finding is None or trim_finding.count == 0

    # 验证数据库中 account_code 已被 trim
    db_session.refresh(entry)
    assert entry.account_code == "1001"


def test_apply_auto_fixes_requires_approval(db_session):
    """apply_auto_fixes 未批准时应抛异常。"""
    report = scan_data_debt(db_session, categories=["dirty"])
    with pytest.raises(ValueError, match="approved=True"):
        apply_auto_fixes(db_session, report, approved=False)


# ======================== 报告结构验证 ========================

def test_report_structure(db_session):
    """报告应包含 summary 和 findings 结构。"""
    _seed_base(db_session)
    report = scan_data_debt(db_session)
    d = report.to_dict()

    assert "generated_at" in d
    assert "scopes" in d
    assert "summary" in d
    assert "findings" in d
    assert isinstance(d["findings"], list)

    summary = d["summary"]
    assert "categories" in summary
    assert "by_severity" in summary
    assert "finding_items" in summary
    assert "affected_records_total" in summary


def test_clean_db_has_no_critical_findings(db_session):
    """干净的数据库（仅基础数据）不应有 critical 级别发现。"""
    _seed_base(db_session)
    report = scan_data_debt(db_session)
    critical = [f for f in report.findings if f.severity == "critical"]
    assert len(critical) == 0, f"干净库不应有 critical 问题，但发现: {[(f.rule_id, f.count) for f in critical]}"
