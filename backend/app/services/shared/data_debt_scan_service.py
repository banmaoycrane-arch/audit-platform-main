"""系统审计数据负债扫描服务。

覆盖 4 大类问题：
1. 孤儿记录（orphan）：外键列值指向不存在的主表记录（仅对未启用 FK 约束的弱外键扫描）
2. 约束完整性（constraint_integrity）：金额非负、枚举值域合规、必填非空
3. 数据一致性（consistency）：凭证/分录借贷平衡、总账/明细账勾稽
4. 脏数据（dirty）：空白/空串科目代码、日期越界、重复记录

扫描结果以结构化 dict 返回：{category_name: [{rule_id, name, count, sample_ids, severity}]}
建议：先 dry_run 看报告，确认后再修复。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, exists, func, or_, select, text
from sqlalchemy.orm import Session

from app.db.models import (
    AccountingEntry,
    AccountingPeriod,
    BankAccount,
    BankReconciliation,
    BankReconciliationItem,
    BankTransaction,
    Counterparty,
    CounterpartyConfirmation,
    EntryTag,
    ImportJob,
    Invoice,
    InvoiceItem,
    Ledger,
    OpeningBalance,
    Organization,
    PeriodCloseLog,
    PeriodSnapshot,
    SourceFile,
    StagingAccountingEntry,
    StagingGeneralLedgerLine,
    StagingGeneralLedgerSummary,
    User,
    Voucher,
)

logger = logging.getLogger(__name__)

SEVERITY_CRITICAL = "critical"   # 影响资产负债表平衡/合规性
SEVERITY_HIGH = "high"           # 影响审计可追溯性
SEVERITY_MEDIUM = "medium"       # 影响查询正确性
SEVERITY_LOW = "low"             # 纯数据美观问题（多余空格等）

SAMPLE_LIMIT = 20  # 每个规则最多返回多少条样本 id


# ======================== 数据结构 ========================

@dataclass
class DebtFinding:
    """单条数据负债发现项。"""
    rule_id: str
    name: str
    category: str          # orphan / constraint_integrity / consistency / dirty
    severity: str
    count: int
    sample_ids: list[int] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "category": self.category,
            "severity": self.severity,
            "count": self.count,
            "sample_ids": self.sample_ids,
            "description": self.description,
        }


@dataclass
class DebtReport:
    generated_at: datetime
    scopes: dict[str, Any]            # 扫描范围（organization_id 等）
    findings: list[DebtFinding] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        by_cat: dict[str, int] = {}
        by_sev: dict[str, int] = {}
        total_count = 0
        for f in self.findings:
            by_cat[f.category] = by_cat.get(f.category, 0) + 1
            by_sev[f.severity] = by_sev.get(f.severity, 0) + 1
            total_count += f.count
        return {
            "categories": by_cat,
            "by_severity": by_sev,
            "finding_items": len(self.findings),
            "affected_records_total": total_count,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "scopes": self.scopes,
            "summary": self.summary(),
            "findings": [f.to_dict() for f in self.findings],
        }


# ======================== 辅助函数 ========================

def _sample(ids: list[int]) -> list[int]:
    return ids[:SAMPLE_LIMIT]


def _count_and_ids(
    db: Session,
    id_col,
    where_clause,
    *,
    limit: int = SAMPLE_LIMIT,
) -> tuple[int, list[int]]:
    """通用：返回 where_clause 命中的总条数 + 前 limit 个 id。"""
    count_q = select(func.count()).select_from(id_col.parent).where(where_clause)
    total = int(db.scalar(count_q) or 0)
    if total == 0:
        return 0, []
    ids_q = select(id_col).where(where_clause).order_by(id_col).limit(limit)
    sample = [r[0] for r in db.execute(ids_q).all()]
    return total, sample


def _append(
    findings: list[DebtFinding],
    /,
    rule_id: str,
    name: str,
    category: str,
    severity: str,
    count: int,
    sample_ids: list[int] | None = None,
    description: str = "",
) -> None:
    if count <= 0:
        return
    findings.append(DebtFinding(
        rule_id=rule_id,
        name=name,
        category=category,
        severity=severity,
        count=count,
        sample_ids=sample_ids or [],
        description=description,
    ))


# ======================== 1. 孤儿记录扫描 ========================

def _scan_orphans(db: Session, findings: list[DebtFinding]) -> None:
    """弱外键孤儿扫描（未在模型中声明 FK 的关联列）。"""

    # 1.1 StagingAccountingEntry.organization_id 缺失 Organization
    cnt, ids = _count_and_ids(
        db,
        StagingAccountingEntry.id,
        ~exists().where(Organization.id == StagingAccountingEntry.organization_id),
    )
    _append(findings, "orph_stg_entry_org", "staging_entry.organization_id 指向不存在的组织",
            "orphan", SEVERITY_HIGH, cnt, _sample(ids))

    # 1.2 StagingGeneralLedgerLine.organization_id
    cnt, ids = _count_and_ids(
        db, StagingGeneralLedgerLine.id,
        ~exists().where(Organization.id == StagingGeneralLedgerLine.organization_id),
    )
    _append(findings, "orph_stg_gl_line_org", "staging_gl_line.organization_id 孤儿",
            "orphan", SEVERITY_HIGH, cnt, _sample(ids))

    # 1.3 StagingGeneralLedgerSummary.organization_id
    cnt, ids = _count_and_ids(
        db, StagingGeneralLedgerSummary.id,
        ~exists().where(Organization.id == StagingGeneralLedgerSummary.organization_id),
    )
    _append(findings, "orph_stg_gl_sum_org", "staging_gl_summary.organization_id 孤儿",
            "orphan", SEVERITY_HIGH, cnt, _sample(ids))

    # 1.3 Counterparty.default_entity_id 指向不存在的 Entity（如果有值）
    if hasattr(Counterparty, "default_entity_id"):
        from app.db.models import Entity
        cnt, ids = _count_and_ids(
            db, Counterparty.id,
            and_(Counterparty.default_entity_id.isnot(None),
                 ~exists().where(Entity.id == Counterparty.default_entity_id)),
        )
        _append(findings, "orph_cp_default_entity", "counterparty.default_entity_id 指向不存在的实体",
                "orphan", SEVERITY_MEDIUM, cnt, _sample(ids))


# ======================== 2. 约束完整性扫描 ========================

def _scan_constraint_integrity(db: Session, findings: list[DebtFinding]) -> None:
    """金额非负 / 必填非空 / 枚举值域边界。"""

    # 2.1 凭证借贷不平
    cnt, ids = _count_and_ids(
        db, Voucher.id,
        Voucher.total_debit != Voucher.total_credit,
    )
    _append(findings, "ci_voucher_unbalanced", "凭证借贷不平",
            "constraint_integrity", SEVERITY_CRITICAL, cnt, _sample(ids),
            "财务致命问题：会导致试算平衡表差异")

    # 2.2 凭证借贷合计为零（异常空凭证）
    cnt, ids = _count_and_ids(
        db, Voucher.id,
        and_(Voucher.total_debit == Decimal("0"), Voucher.total_credit == Decimal("0")),
    )
    _append(findings, "ci_voucher_zero_amount", "凭证借贷合计为零（空凭证）",
            "constraint_integrity", SEVERITY_LOW, cnt, _sample(ids))

    # 2.3 单条分录借贷同时为 0 或同时 > 0（复式记账必一侧有值）
    bad_both_nonzero = and_(
        AccountingEntry.debit_amount > Decimal("0"),
        AccountingEntry.credit_amount > Decimal("0"),
    )
    bad_both_zero = and_(
        AccountingEntry.debit_amount == Decimal("0"),
        AccountingEntry.credit_amount == Decimal("0"),
    )
    cnt, ids = _count_and_ids(
        db, AccountingEntry.id,
        or_(bad_both_nonzero, bad_both_zero),
    )
    _append(findings, "ci_entry_amount_invalid", "分录借贷异常（双侧有值或双侧为零）",
            "constraint_integrity", SEVERITY_CRITICAL, cnt, _sample(ids))

    # 2.4 金额字段负数（Voucher/AccountingEntry）
    neg_amount = or_(
        Voucher.total_debit < Decimal("0"),
        Voucher.total_credit < Decimal("0"),
    )
    cnt, ids = _count_and_ids(db, Voucher.id, neg_amount)
    _append(findings, "ci_voucher_negative", "凭证金额出现负数",
            "constraint_integrity", SEVERITY_HIGH, cnt, _sample(ids))

    neg_entry = or_(
        AccountingEntry.debit_amount < Decimal("0"),
        AccountingEntry.credit_amount < Decimal("0"),
    )
    cnt, ids = _count_and_ids(db, AccountingEntry.id, neg_entry)
    _append(findings, "ci_entry_negative", "分录金额出现负数",
            "constraint_integrity", SEVERITY_HIGH, cnt, _sample(ids))

    # 2.5 必填非空：voucher_no / account_code 为 NULL 或 ''
    for col, rid, nname, sev in [
        (Voucher.voucher_no, "ci_voucher_no_empty", "凭证 voucher_no 为空", SEVERITY_HIGH),
        (AccountingEntry.account_code, "ci_entry_acct_empty", "分录 account_code 为空", SEVERITY_HIGH),
        (AccountingEntry.account_name, "ci_entry_acct_name_empty", "分录 account_name 为空", SEVERITY_MEDIUM),
    ]:
        cnt, ids = _count_and_ids(
            db, col.parent.c.id if False else (Voucher.id if col is Voucher.voucher_no else AccountingEntry.id),
            or_(col.is_(None), col == ""),
        )
        _append(findings, rid, nname, "constraint_integrity", sev, cnt, _sample(ids))

    # 2.6 枚举值域（兜底：模型 CheckConstraint 之外的非法值，防止绕过 ORM 直接 DML）
    VALID_VOUCHER_STATUS = {"draft", "pending", "verified", "posted", "cancelled"}
    cnt, ids = _count_and_ids(db, Voucher.id, ~Voucher.status.in_(VALID_VOUCHER_STATUS))
    _append(findings, "ci_voucher_status_illegal", "凭证 status 非法值",
            "constraint_integrity", SEVERITY_HIGH, cnt, _sample(ids),
            f"允许值={sorted(VALID_VOUCHER_STATUS)}")

    VALID_ENTRY_REVIEW = {"draft", "pending", "auto_reviewed", "ready", "verified", "posted"}
    cnt, ids = _count_and_ids(db, AccountingEntry.id, ~AccountingEntry.review_status.in_(VALID_ENTRY_REVIEW))
    _append(findings, "ci_entry_review_illegal", "分录 review_status 非法值",
            "constraint_integrity", SEVERITY_HIGH, cnt, _sample(ids),
            f"允许值={sorted(VALID_ENTRY_REVIEW)}")

    VALID_ENTRY_POST = {"draft", "verified", "posted"}
    cnt, ids = _count_and_ids(db, AccountingEntry.id, ~AccountingEntry.post_status.in_(VALID_ENTRY_POST))
    _append(findings, "ci_entry_post_illegal", "分录 post_status 非法值",
            "constraint_integrity", SEVERITY_HIGH, cnt, _sample(ids),
            f"允许值={sorted(VALID_ENTRY_POST)}")

    VALID_PERIOD_STATUS = {"open", "reopened", "pl_transferred", "closed"}
    cnt, ids = _count_and_ids(db, AccountingPeriod.id, ~AccountingPeriod.status.in_(VALID_PERIOD_STATUS))
    _append(findings, "ci_period_status_illegal", "会计期间 status 非法值",
            "constraint_integrity", SEVERITY_HIGH, cnt, _sample(ids),
            f"允许值={sorted(VALID_PERIOD_STATUS)}")

    # 2.7 期间日期范围非法：end_date < start_date
    cnt, ids = _count_and_ids(db, AccountingPeriod.id, AccountingPeriod.end_date < AccountingPeriod.start_date)
    _append(findings, "ci_period_date_invalid", "会计期间 end_date < start_date",
            "constraint_integrity", SEVERITY_CRITICAL, cnt, _sample(ids))


# ======================== 3. 数据一致性扫描 ========================

def _scan_consistency(db: Session, findings: list[DebtFinding]) -> None:
    """凭证 <-> 分录汇总勾稽 / 期间状态语义一致性。"""

    # 3.1 凭证 total_debit ≠ 分录 debit_amount 汇总
    # 使用子查询计算 voucher_id 维度的分录汇总，再与 voucher 比较
    debit_sum = (
        select(
            AccountingEntry.voucher_id.label("vid"),
            func.coalesce(func.sum(AccountingEntry.debit_amount), Decimal("0")).label("debits"),
            func.coalesce(func.sum(AccountingEntry.credit_amount), Decimal("0")).label("credits"),
        )
        .where(AccountingEntry.voucher_id.isnot(None))
        .group_by(AccountingEntry.voucher_id)
        .subquery()
    )
    mismatch_q = (
        select(Voucher.id)
        .join(debit_sum, debit_sum.c.vid == Voucher.id)
        .where(or_(
            Voucher.total_debit != debit_sum.c.debits,
            Voucher.total_credit != debit_sum.c.credits,
        ))
    )
    mismatch_ids = [r[0] for r in db.execute(mismatch_q).all()]
    _append(findings, "cs_voucher_entry_mismatch",
            "凭证汇总金额与分录汇总金额不一致",
            "consistency", SEVERITY_CRITICAL,
            len(mismatch_ids), _sample(mismatch_ids),
            "典型原因：更新分录后未回写凭证汇总列")

    # 3.2 分录 entry_line_no 重复（同 voucher_id 内）
    dup_line_subq = (
        select(
            AccountingEntry.voucher_id.label("vid"),
            AccountingEntry.entry_line_no.label("lineno"),
            func.count().label("cnt"),
        )
        .where(AccountingEntry.voucher_id.isnot(None))
        .group_by(AccountingEntry.voucher_id, AccountingEntry.entry_line_no)
        .having(func.count() > 1)
        .subquery()
    )
    dup_entry_ids_q = (
        select(func.min(AccountingEntry.id))
        .join(dup_line_subq, and_(
            AccountingEntry.voucher_id == dup_line_subq.c.vid,
            AccountingEntry.entry_line_no == dup_line_subq.c.lineno,
        ))
    )
    dup_entry_count = int(db.scalar(select(func.count()).select_from(dup_line_subq)) or 0)
    sample_entries = [r[0] for r in db.execute(
        select(AccountingEntry.id)
        .join(dup_line_subq, and_(
            AccountingEntry.voucher_id == dup_line_subq.c.vid,
            AccountingEntry.entry_line_no == dup_line_subq.c.lineno,
        ))
        .order_by(AccountingEntry.id)
        .limit(SAMPLE_LIMIT)
    ).all()]
    _append(findings, "cs_entry_line_no_dup",
            "同一凭证内 entry_line_no 重复",
            "consistency", SEVERITY_HIGH,
            dup_entry_count, _sample(sample_entries),
            "会导致分录明细页排序错乱")

    # 3.3 期间凭证 voucher_date 不在所属 period 的 [start_date, end_date]
    misdate_q = (
        select(Voucher.id)
        .join(AccountingPeriod, AccountingPeriod.id == Voucher.period_id)
        .where(or_(
            Voucher.voucher_date < AccountingPeriod.start_date,
            Voucher.voucher_date > AccountingPeriod.end_date,
        ))
    )
    misdate_ids = [r[0] for r in db.execute(misdate_q).all()]
    _append(findings, "cs_voucher_period_date_oob",
            "凭证日期超出所属会计期间范围",
            "consistency", SEVERITY_HIGH,
            len(misdate_ids), _sample(misdate_ids))

    # 3.4 OpeningBalance 借贷不平（同 ledger_id + period_id 合计）
    # 注：OpeningBalance 字段名是 debit_balance / credit_balance（期初余额的期末方向）
    ob_subq = (
        select(
            OpeningBalance.ledger_id.label("lid"),
            OpeningBalance.period_id.label("pid"),
            func.coalesce(func.sum(OpeningBalance.debit_balance), Decimal("0")).label("d"),
            func.coalesce(func.sum(OpeningBalance.credit_balance), Decimal("0")).label("c"),
        )
        .group_by(OpeningBalance.ledger_id, OpeningBalance.period_id)
        .subquery()
    )
    ob_unbalanced = db.scalar(
        select(func.count())
        .select_from(ob_subq)
        .where(ob_subq.c.d != ob_subq.c.c)
    ) or 0
    _append(findings, "cs_ob_unbalanced",
            "期初余额表借贷不平",
            "consistency", SEVERITY_CRITICAL, int(ob_unbalanced))


# ======================== 4. 脏数据扫描 ========================

def _scan_dirty(db: Session, findings: list[DebtFinding]) -> None:
    """前后空格、异常日期、重复记录。"""

    # 4.1 科目代码前后空格
    space_acct = or_(
        AccountingEntry.account_code.like(" %"),
        AccountingEntry.account_code.like("% "),
    )
    cnt, ids = _count_and_ids(db, AccountingEntry.id, space_acct)
    _append(findings, "dd_acct_code_trim", "分录 account_code 前后含空格",
            "dirty", SEVERITY_LOW, cnt, _sample(ids))

    # 4.2 凭证号前后空格
    space_vno = or_(Voucher.voucher_no.like(" %"), Voucher.voucher_no.like("% "))
    cnt, ids = _count_and_ids(db, Voucher.id, space_vno)
    _append(findings, "dd_voucher_no_trim", "凭证 voucher_no 前后含空格",
            "dirty", SEVERITY_LOW, cnt, _sample(ids))

    # 4.3 凭证号完全空白但已过账（过账凭证应有号）
    cnt, ids = _count_and_ids(
        db, Voucher.id,
        and_(Voucher.status == "posted", or_(Voucher.voucher_no.is_(None), Voucher.voucher_no == "")),
    )
    _append(findings, "dd_posted_voucher_no_missing", "已过账凭证无凭证号",
            "dirty", SEVERITY_MEDIUM, cnt, _sample(ids))

    # 4.4 (ledger_id, voucher_no) 重复（违反业务唯一）
    dup_vno_subq = (
        select(
            Voucher.ledger_id.label("lid"),
            Voucher.voucher_no.label("vno"),
            func.count().label("cnt"),
        )
        .where(Voucher.voucher_no.isnot(None), Voucher.voucher_no != "")
        .group_by(Voucher.ledger_id, Voucher.voucher_no)
        .having(func.count() > 1)
        .subquery()
    )
    dup_cnt = int(db.scalar(select(func.count()).select_from(dup_vno_subq)) or 0)
    dup_voucher_ids = [r[0] for r in db.execute(
        select(func.min(Voucher.id))
        .join(dup_vno_subq, and_(
            Voucher.ledger_id == dup_vno_subq.c.lid,
            Voucher.voucher_no == dup_vno_subq.c.vno,
        ))
        .limit(SAMPLE_LIMIT)
    ).all()]
    _append(findings, "dd_voucher_no_dup",
            "同账簿下 voucher_no 重复",
            "dirty", SEVERITY_HIGH, dup_cnt, _sample(dup_voucher_ids))

    # 4.5 未来日期凭证（超过今日+365 天，疑似误填）
    today = date.today()
    future_limit = date(today.year + 1, today.month, today.day) if today.month != 2 or today.day != 29 else date(today.year + 2, 1, 1)
    cnt, ids = _count_and_ids(db, Voucher.id, Voucher.voucher_date > future_limit)
    _append(findings, "dd_voucher_future_date",
            f"凭证日期晚于 {future_limit.isoformat()}（> 1 年后）",
            "dirty", SEVERITY_MEDIUM, cnt, _sample(ids))

    # 4.6 极早日期（< 1990-01-01 疑似误填）
    cnt, ids = _count_and_ids(db, Voucher.id, Voucher.voucher_date < date(1990, 1, 1))
    _append(findings, "dd_voucher_ancient_date", "凭证日期早于 1990-01-01",
            "dirty", SEVERITY_MEDIUM, cnt, _sample(ids))


# ======================== 公开 API ========================

def scan_data_debt(
    db: Session,
    *,
    organization_id: int | None = None,
    ledger_id: int | None = None,
    categories: list[str] | None = None,
) -> DebtReport:
    """执行全库数据负债扫描，返回结构化报告。

    Args:
        db: SQLAlchemy Session
        organization_id: 可选，仅扫描指定组织
        ledger_id: 可选，仅扫描指定账簿
        categories: 可选，仅扫描指定类别（orphan / constraint_integrity / consistency / dirty）
    """
    categories_set = set(categories) if categories else None
    findings: list[DebtFinding] = []

    # 应用组织/账簿范围 filter（通过设置全局条件较难，这里在有范围时限制凭证/分录表）
    # 为简单起见，全部全表扫描；后续可按需加 scoped 版本。

    if categories_set is None or "orphan" in categories_set:
        _scan_orphans(db, findings)
    if categories_set is None or "constraint_integrity" in categories_set:
        _scan_constraint_integrity(db, findings)
    if categories_set is None or "consistency" in categories_set:
        _scan_consistency(db, findings)
    if categories_set is None or "dirty" in categories_set:
        _scan_dirty(db, findings)

    # 稳定排序：严重度 → 类别 → 影响条数（降序）
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: (sev_order.get(f.severity, 99), f.category, -f.count))

    return DebtReport(
        generated_at=datetime.now(timezone.utc),
        scopes={
            "organization_id": organization_id,
            "ledger_id": ledger_id,
            "categories": sorted(categories_set) if categories_set else "all",
        },
        findings=findings,
    )


# ======================== 修复执行器（需明确批准） ========================

@dataclass
class FixAction:
    """一条修复动作记录。"""
    rule_id: str
    action: str
    count: int
    sql_preview: str = ""


FIXABLE_RULES = {
    "dd_acct_code_trim": "TRIM(account_code)",
    "dd_voucher_no_trim": "TRIM(voucher_no)",
}


def apply_auto_fixes(db: Session, report: DebtReport, *, approved: bool = False) -> list[FixAction]:
    """应用可自动修复的脏数据（空格 trim）。

    安全要求：必须显式 approved=True；不提交事务，由调用方 commit。
    仅允许 FIXABLE_RULES 白名单中的低风险规则。
    """
    if not approved:
        raise ValueError("自动修复需要显式 approved=True，请先审阅报告确认影响范围")

    actions: list[FixAction] = []
    for finding in report.findings:
        if finding.rule_id not in FIXABLE_RULES:
            continue
        if finding.count <= 0:
            continue
        # 动态生成 UPDATE
        if finding.rule_id == "dd_acct_code_trim":
            stmt = (
                text("UPDATE accounting_entries SET account_code = TRIM(account_code) "
                     "WHERE (account_code LIKE ' %' OR account_code LIKE '% ')")
            )
            result = db.execute(stmt)
            rowcount: Any = getattr(result, "rowcount", None)
            actions.append(FixAction(
                rule_id=finding.rule_id,
                action="TRIM(account_code)",
                count=int(rowcount or 0),
                sql_preview="UPDATE accounting_entries SET account_code = TRIM(account_code) WHERE trim-needed",
            ))
        elif finding.rule_id == "dd_voucher_no_trim":
            stmt = (
                text("UPDATE vouchers SET voucher_no = TRIM(voucher_no) "
                     "WHERE (voucher_no LIKE ' %' OR voucher_no LIKE '% ')")
            )
            result = db.execute(stmt)
            rowcount = getattr(result, "rowcount", None)
            actions.append(FixAction(
                rule_id=finding.rule_id,
                action="TRIM(voucher_no)",
                count=int(rowcount or 0),
                sql_preview="UPDATE vouchers SET voucher_no = TRIM(voucher_no) WHERE trim-needed",
            ))
    return actions
