# -*- coding: utf-8 -*-
"""
多维度管理分析服务（Analytics Service）。

业务场景：
    基于已打标签的凭证数据，提供客户往来分析、项目成本分析等管理视图，
    支持数据筛选、钻取、导出。

政策依据：
    分析视图基于 EntryTag 维度聚合，不改变会计凭证的借贷平衡与法定报表，
    仅用于管理决策和审计分析。

输入数据：
    - ledger_id: 账簿 ID
    - category_code: 分析维度（counterparty / project 等）
    - start_date / end_date: 时间范围
    - account_code_prefix: 科目前缀过滤

输出结果：
    - 聚合后的维度分析数据及明细钻取数据
"""
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from app.db.models import AccountingEntry, EntryTag, TagCategory


def _sum_decimal(column) -> Decimal:
    """
    将 SQL sum 结果转换为 Decimal。
    """
    return Decimal(str(column or 0))


def _get_category_id(db: Session, ledger_id: int, category_code: str) -> int | None:
    """
    根据 ledger_id 和 category_code 获取分类 ID。
    """
    category = (
        db.query(TagCategory)
        .filter(
            TagCategory.ledger_id == ledger_id,
            TagCategory.code == category_code.strip().lower(),
        )
        .first()
    )
    return category.id if category else None


def analyze_counterparty(
    db: Session,
    ledger_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    account_code_prefix: str | None = None,
    counterparty_value: str | None = None,
) -> list[dict[str, Any]]:
    """
    客户往来分析视图。

    聚合逻辑：
        - 按 counterparty tag 分组
        - 分别汇总应收账款（1122 借方/贷方）、应付账款（2202 贷方/借方）、
          预收账款（2203）、预付账款（1123）等往来科目的发生额
        - 计算期末应收/应付净额

    Args:
        db: 数据库会话
        ledger_id: 账簿 ID
        start_date / end_date: 凭证日期范围
        account_code_prefix: 科目编码前缀过滤
        counterparty_value: 指定单个往来单位

    Returns:
        每个往来单位的汇总数据列表
    """
    category_id = _get_category_id(db, ledger_id, "counterparty")
    if category_id is None:
        return []

    query = (
        db.query(
            EntryTag.tag_value.label("counterparty"),
            func.sum(AccountingEntry.debit_amount).label("total_debit"),
            func.sum(AccountingEntry.credit_amount).label("total_credit"),
            func.count(AccountingEntry.id).label("entry_count"),
        )
        .join(AccountingEntry, EntryTag.entry_id == AccountingEntry.id)
        .filter(
            EntryTag.ledger_id == ledger_id,
            EntryTag.category_id == category_id,
            AccountingEntry.ledger_id == ledger_id,
        )
    )

    if start_date:
        query = query.filter(AccountingEntry.voucher_date >= start_date)
    if end_date:
        query = query.filter(AccountingEntry.voucher_date <= end_date)
    if account_code_prefix:
        query = query.filter(AccountingEntry.account_code.like(f"{account_code_prefix}%"))
    if counterparty_value:
        query = query.filter(EntryTag.tag_value == counterparty_value)

    rows = (
        query.group_by(EntryTag.tag_value)
        .order_by(func.sum(AccountingEntry.debit_amount + AccountingEntry.credit_amount).desc())
        .all()
    )

    result: list[dict[str, Any]] = []
    for row in rows:
        total_debit = _sum_decimal(row.total_debit)
        total_credit = _sum_decimal(row.total_credit)
        result.append({
            "counterparty": row.counterparty,
            "total_debit": float(total_debit),
            "total_credit": float(total_credit),
            "net_receivable_payable": float(total_debit - total_credit),
            "entry_count": row.entry_count,
        })
    return result


def drill_down_counterparty(
    db: Session,
    ledger_id: int,
    counterparty_value: str,
    start_date: date | None = None,
    end_date: date | None = None,
    account_code_prefix: str | None = None,
) -> list[dict[str, Any]]:
    """
    客户往来明细钻取。
    """
    category_id = _get_category_id(db, ledger_id, "counterparty")
    if category_id is None:
        return []

    query = (
        db.query(AccountingEntry)
        .join(EntryTag, AccountingEntry.id == EntryTag.entry_id)
        .filter(
            EntryTag.ledger_id == ledger_id,
            EntryTag.category_id == category_id,
            EntryTag.tag_value == counterparty_value,
            AccountingEntry.ledger_id == ledger_id,
        )
    )

    if start_date:
        query = query.filter(AccountingEntry.voucher_date >= start_date)
    if end_date:
        query = query.filter(AccountingEntry.voucher_date <= end_date)
    if account_code_prefix:
        query = query.filter(AccountingEntry.account_code.like(f"{account_code_prefix}%"))

    entries = query.order_by(AccountingEntry.voucher_date, AccountingEntry.voucher_no).all()
    return [
        {
            "entry_id": e.id,
            "voucher_no": e.voucher_no,
            "voucher_date": str(e.voucher_date) if e.voucher_date else None,
            "account_code": e.account_code,
            "account_name": e.account_name,
            "summary": e.summary,
            "debit_amount": float(e.debit_amount or 0),
            "credit_amount": float(e.credit_amount or 0),
            "counterparty": e.counterparty,
        }
        for e in entries
    ]


def analyze_project_cost(
    db: Session,
    ledger_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    project_value: str | None = None,
) -> list[dict[str, Any]]:
    """
    项目成本分析视图。

    聚合逻辑：
        - 按 project tag 分组
        - 汇总成本类（4xxx）和损益类费用科目（660x 等）的借方发生额
        - 按 business_type tag 拆分成本构成
        - 提供项目总成本及明细成本构成

    Args:
        db: 数据库会话
        ledger_id: 账簿 ID
        start_date / end_date: 凭证日期范围
        project_value: 指定单个项目

    Returns:
        每个项目的成本汇总数据列表
    """
    project_category_id = _get_category_id(db, ledger_id, "project")
    if project_category_id is None:
        return []

    # 子查询：按项目和 business_type 聚合
    business_type_id = _get_category_id(db, ledger_id, "business_type")

    query = (
        db.query(
            EntryTag.tag_value.label("project"),
            func.sum(AccountingEntry.debit_amount).label("total_cost"),
            func.count(AccountingEntry.id).label("entry_count"),
        )
        .join(AccountingEntry, EntryTag.entry_id == AccountingEntry.id)
        .filter(
            EntryTag.ledger_id == ledger_id,
            EntryTag.category_id == project_category_id,
            AccountingEntry.ledger_id == ledger_id,
            # 成本类或费用类科目前缀
            AccountingEntry.account_code.like("4%") | AccountingEntry.account_code.like("5%") | AccountingEntry.account_code.like("660%"),
        )
    )

    if start_date:
        query = query.filter(AccountingEntry.voucher_date >= start_date)
    if end_date:
        query = query.filter(AccountingEntry.voucher_date <= end_date)
    if project_value:
        query = query.filter(EntryTag.tag_value == project_value)

    rows = (
        query.group_by(EntryTag.tag_value)
        .order_by(func.sum(AccountingEntry.debit_amount).desc())
        .all()
    )

    # 一次性查询所有项目的成本构成，避免循环内多次查询
    breakdown_map: dict[str, list[dict[str, Any]]] = {}
    if business_type_id:
        # 使用别名 join 同一张 EntryTag 表
        project_tag_alias = aliased(EntryTag)

        breakdown_query = (
            db.query(
                project_tag_alias.tag_value.label("project"),
                EntryTag.tag_value.label("business_type"),
                func.sum(AccountingEntry.debit_amount).label("cost"),
            )
            .select_from(AccountingEntry)
            .join(project_tag_alias, AccountingEntry.id == project_tag_alias.entry_id)
            .join(EntryTag, AccountingEntry.id == EntryTag.entry_id)
            .filter(
                project_tag_alias.ledger_id == ledger_id,
                project_tag_alias.category_id == project_category_id,
                EntryTag.ledger_id == ledger_id,
                EntryTag.category_id == business_type_id,
                AccountingEntry.ledger_id == ledger_id,
                AccountingEntry.account_code.like("4%")
                | AccountingEntry.account_code.like("5%")
                | AccountingEntry.account_code.like("660%"),
            )
        )
        if start_date:
            breakdown_query = breakdown_query.filter(AccountingEntry.voucher_date >= start_date)
        if end_date:
            breakdown_query = breakdown_query.filter(AccountingEntry.voucher_date <= end_date)
        if project_value:
            breakdown_query = breakdown_query.filter(project_tag_alias.tag_value == project_value)

        breakdown_rows = breakdown_query.group_by(
            project_tag_alias.tag_value, EntryTag.tag_value
        ).all()

        for br in breakdown_rows:
            breakdown_map.setdefault(br.project, []).append({
                "business_type": br.business_type,
                "cost": float(_sum_decimal(br.cost)),
            })

    result: list[dict[str, Any]] = []
    for row in rows:
        project_name = row.project
        result.append({
            "project": project_name,
            "total_cost": float(_sum_decimal(row.total_cost)),
            "entry_count": row.entry_count,
            "cost_breakdown": breakdown_map.get(project_name, []),
            "budget_amount": None,  # 预算金额待后续扩展
            "budget_execution_rate": None,  # 预算执行率待后续扩展
        })
    return result


def drill_down_project_cost(
    db: Session,
    ledger_id: int,
    project_value: str,
    start_date: date | None = None,
    end_date: date | None = None,
    business_type: str | None = None,
) -> list[dict[str, Any]]:
    """
    项目成本明细钻取。
    """
    project_category_id = _get_category_id(db, ledger_id, "project")
    if project_category_id is None:
        return []

    query = (
        db.query(AccountingEntry)
        .join(EntryTag, AccountingEntry.id == EntryTag.entry_id)
        .filter(
            EntryTag.ledger_id == ledger_id,
            EntryTag.category_id == project_category_id,
            EntryTag.tag_value == project_value,
            AccountingEntry.ledger_id == ledger_id,
            AccountingEntry.account_code.like("4%")
            | AccountingEntry.account_code.like("5%")
            | AccountingEntry.account_code.like("660%"),
        )
    )

    if start_date:
        query = query.filter(AccountingEntry.voucher_date >= start_date)
    if end_date:
        query = query.filter(AccountingEntry.voucher_date <= end_date)

    if business_type:
        business_type_id = _get_category_id(db, ledger_id, "business_type")
        if business_type_id:
            query = query.join(
                EntryTag,
                (AccountingEntry.id == EntryTag.entry_id)
                & (EntryTag.category_id == business_type_id)
                & (EntryTag.tag_value == business_type),
            )

    entries = query.order_by(AccountingEntry.voucher_date, AccountingEntry.voucher_no).all()
    return [
        {
            "entry_id": e.id,
            "voucher_no": e.voucher_no,
            "voucher_date": str(e.voucher_date) if e.voucher_date else None,
            "account_code": e.account_code,
            "account_name": e.account_name,
            "summary": e.summary,
            "debit_amount": float(e.debit_amount or 0),
            "credit_amount": float(e.credit_amount or 0),
        }
        for e in entries
    ]
