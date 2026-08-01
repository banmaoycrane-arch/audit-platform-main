# -*- coding: utf-8 -*-
"""经济事件工单 — 导入聚类服务（E2）。

业务场景：导入分录入账后，按「往来 + 月份」规则聚类，生成候选事件供人工确认。
会计口径：聚类只发生在已入账分录（AccountingEntry）上，不能在草稿阶段做。
          已挂在 import_cluster 事件上的分录不会被二次聚类（幂等）。
设计决策：D1 往来+月份 / D2 阈值≥2 / D4 规则命名（不内置 LLM）
创建日期：2026-08-01
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AccountingEntry,
    EconomicEvent,
    EconomicEventEntry,
)
from app.services.shared import economic_event_service as svc


@dataclass
class ClusterSuggestion:
    """聚类候选事件（未落库，仅展示）。"""

    cluster_key: str  # "cp:{id_or_name}|ym:{yyyy-mm}"
    title: str
    event_type: str  # 默认 'manual'（D4：不内置 LLM）
    occurred_on: date | None
    counterparty_name: str
    import_job_id: int | None
    entry_ids: list[int] = field(default_factory=list)
    entry_count: int = 0
    display_amount: Decimal = Decimal("0.00")

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_key": self.cluster_key,
            "title": self.title,
            "event_type": self.event_type,
            "occurred_on": self.occurred_on.isoformat() if self.occurred_on else None,
            "counterparty_name": self.counterparty_name,
            "import_job_id": self.import_job_id,
            "entry_ids": list(self.entry_ids),
            "entry_count": self.entry_count,
            "display_amount": str(self.display_amount),
        }


@dataclass
class ClusterConfirmItem:
    """人工确认要创建的聚类项。"""

    title: str
    event_type: str = "manual"
    occurred_on: date | None = None
    entry_ids: list[int] = field(default_factory=list)


def _cluster_label(counterparty_name: str, ym: str) -> str:
    """生成候选事件标题（D4 规则模板）。"""
    cp = counterparty_name or "未命名往来"
    return f"{cp} {ym} 业务"


def suggest_clusters(
    db: Session,
    ledger_id: int,
    *,
    import_job_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    min_entries: int = 2,
) -> list[ClusterSuggestion]:
    """按往来+月份聚类已入账分录，返回候选事件列表（不落库）。

    幂等规则：已挂在任意 import_cluster 类型事件上的分录会被排除，避免重复聚类。
    """
    # 1. 找出已经挂在 import_cluster 事件上的分录 ID（幂等排除集）
    excluded_entry_ids_subq = (
        db.query(EconomicEventEntry.accounting_entry_id)
        .join(EconomicEvent, EconomicEvent.id == EconomicEventEntry.event_id)
        .filter(
            EconomicEvent.ledger_id == ledger_id,
            EconomicEvent.event_type == "import_cluster",
        )
    ).subquery()

    # 2. 查询符合条件的未聚类分录
    q = db.query(AccountingEntry).filter(
        AccountingEntry.ledger_id == ledger_id,
        AccountingEntry.voucher_date.isnot(None),
        ~AccountingEntry.id.in_(select(excluded_entry_ids_subq)),
    )
    if import_job_id is not None:
        q = q.filter(AccountingEntry.import_job_id == import_job_id)
    if date_from is not None:
        q = q.filter(AccountingEntry.voucher_date >= date_from)
    if date_to is not None:
        q = q.filter(AccountingEntry.voucher_date <= date_to)

    entries = q.order_by(AccountingEntry.voucher_date.asc()).all()

    # 3. 按往来+月份分组
    # cluster_key = "cp:{counterparty_id_or_name}|ym:{yyyy-mm}"
    groups: dict[str, list[AccountingEntry]] = {}
    for entry in entries:
        # 往来键：counterparty_id 优先，否则 original_entity_name，再否则 counterparty，最后 "未命名"
        if entry.counterparty_id is not None:
            cp_key = f"id:{entry.counterparty_id}"
            cp_name = entry.counterparty or entry.original_entity_name or "未命名往来"
        else:
            raw_name = (entry.original_entity_name or entry.counterparty or "").strip()
            cp_key = f"name:{raw_name or '未命名'}"
            cp_name = raw_name or "未命名往来"

        ym = entry.voucher_date.strftime("%Y-%m")  # type: ignore[union-attr]
        cluster_key = f"cp:{cp_key}|ym:{ym}"
        groups.setdefault(cluster_key, []).append(entry)

    # 4. 过滤阈值 + 组装候选
    suggestions: list[ClusterSuggestion] = []
    for cluster_key, group in groups.items():
        if len(group) < min_entries:
            continue
        first = group[0]
        cp_name = (
            (first.counterparty or first.original_entity_name or "未命名往来")
            if first.counterparty_id is not None
            else (first.original_entity_name or first.counterparty or "未命名往来")
        )
        ym = first.voucher_date.strftime("%Y-%m")  # type: ignore[union-attr]
        # 金额合计：借方求和（与 compute_display_amount 口径一致）
        total = sum((e.debit_amount for e in group), Decimal("0.00"))
        # import_job_id：组内可能多批次，取第一个非空
        ij_id = next((e.import_job_id for e in group if e.import_job_id is not None), None)
        # occurred_on：取组内最早分录日期
        occurred = min(e.voucher_date for e in group if e.voucher_date)  # type: ignore[arg-type]
        suggestions.append(ClusterSuggestion(
            cluster_key=cluster_key,
            title=_cluster_label(cp_name, ym),
            event_type="manual",  # D4：不内置 LLM，统一 manual；导入聚类来源靠 source 字段标识
            occurred_on=occurred,
            counterparty_name=cp_name,
            import_job_id=ij_id,
            entry_ids=[e.id for e in group],
            entry_count=len(group),
            display_amount=total,
        ))

    # 按发生日升序，便于人工复核
    suggestions.sort(key=lambda s: (s.occurred_on or date.min, s.cluster_key))
    return suggestions


def confirm_clusters(
    db: Session,
    ledger_id: int,
    clusters: list[ClusterConfirmItem],
    *,
    actor_user_id: int | None = None,
    import_job_id: int | None = None,
) -> list[EconomicEvent]:
    """根据人工确认的候选，批量创建事件 + 挂分录 + 推进到 collecting。

    关键约束：
    - 事件 event_type 强制为 'import_cluster'（区分手工事件）
    - source='import'，source_id=import_job_id（追溯触发源）
    - 创建后立即推进 draft → collecting，并写入 step 日志
    - 挂分录调用 svc.attach_entry，自动去重（unique 约束兜底）
    """
    if not clusters:
        return []

    created: list[EconomicEvent] = []
    for item in clusters:
        if not item.entry_ids:
            continue
        # 1. 创建草稿事件（event_type 强制 import_cluster）
        event = svc.create_event(
            db,
            ledger_id=ledger_id,
            title=item.title,
            event_type="import_cluster",
            occurred_on=item.occurred_on,
            summary=f"导入聚类生成：{item.title}",
            source="import",
            source_id=import_job_id,
            created_by=actor_user_id,
        )
        # 2. 挂分录
        for entry_id in item.entry_ids:
            svc.attach_entry(
                db, event.id, entry_id,
                relation_type="primary",
                actor_user_id=actor_user_id,
            )
        # 3. 推进到 collecting（一次状态机迁移 + step 日志）
        event = svc.transition(
            db, event.id, "collecting",
            actor_user_id=actor_user_id,
            actor_type="user",
            reason=f"导入聚类自动归集：{len(item.entry_ids)} 条分录",
        )
        created.append(event)

    return created
