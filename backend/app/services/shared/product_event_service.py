# -*- coding: utf-8 -*-
"""产品埋点：MVP 验证用事件存储与 KPI 聚合。"""
from __future__ import annotations

from datetime import datetime, timedelta
from statistics import median
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ProductEvent


def record_product_event(
    db: Session,
    *,
    event_name: str,
    user_id: int | None = None,
    team_id: int | None = None,
    ledger_id: int | None = None,
    job_id: int | None = None,
    session_id: str | None = None,
    properties: dict[str, Any] | None = None,
) -> ProductEvent:
    event = ProductEvent(
        event_name=event_name,
        user_id=user_id,
        team_id=team_id,
        ledger_id=ledger_id,
        job_id=job_id,
        session_id=session_id,
        properties=properties or {},
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def _since(days: int) -> datetime:
    return datetime.utcnow() - timedelta(days=days)


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def get_mvp_kpi_summary(
    db: Session,
    *,
    days: int = 14,
    ledger_id: int | None = None,
) -> dict[str, Any]:
    """聚合两周 MVP 验证 KPI，便于决策者识别通过/失败。"""
    since = _since(days)
    base = select(ProductEvent).where(ProductEvent.created_at >= since)
    if ledger_id is not None:
        base = base.where(ProductEvent.ledger_id == ledger_id)

    events = list(db.scalars(base.order_by(ProductEvent.created_at.desc()).limit(5000)))

    by_name: dict[str, list[ProductEvent]] = {}
    for event in events:
        by_name.setdefault(event.event_name, []).append(event)

    draft_shown = by_name.get("ai_voucher_draft_shown", [])
    draft_saved = by_name.get("ai_voucher_draft_saved", [])
    step_events = by_name.get("task_bookkeeping_step_reached", [])
    agent_sessions = by_name.get("agent_assist_session", [])
    path_clicks = by_name.get("agent_suggested_path_click", [])

    adoption_ratios: list[float] = []
    for event in draft_saved:
        props = event.properties or {}
        total = _num(props.get("fields_total"))
        adopted = _num(props.get("fields_adopted_unchanged"))
        if total > 0:
            adoption_ratios.append(adopted / total)

    step1_jobs = {
        e.job_id for e in step_events
        if (e.properties or {}).get("step") == "step1_select" and e.job_id
    }
    step5_jobs = {
        e.job_id for e in step_events
        if (e.properties or {}).get("step") == "step5_post" and e.job_id
    }
    step1_sessions = {
        f"u{e.user_id}:{(e.properties or {}).get('step')}"
        for e in step_events
        if (e.properties or {}).get("step") == "step1_select" and not e.job_id
    }
    step5_sessions = {
        f"u{e.user_id}:{(e.properties or {}).get('step')}"
        for e in step_events
        if (e.properties or {}).get("step") == "step5_post" and not e.job_id
    }
    step1_count = len(step1_jobs) + len(step1_sessions)
    step5_count = len(step5_jobs) + len(step5_sessions)

    suggest_success = [
        e for e in agent_sessions
        if (e.properties or {}).get("suggested_path")
    ]
    clicked_paths = len(path_clicks)

    rounds_by_session: dict[str, list[int]] = {}
    for event in agent_sessions:
        sid = event.session_id or f"anon-{event.id}"
        rnd = int(_num((event.properties or {}).get("round_index")) or 1)
        rounds_by_session.setdefault(sid, []).append(rnd)
    session_max_rounds = [max(v) for v in rounds_by_session.values() if v]

    ai_adoption_rate = round(sum(adoption_ratios) / len(adoption_ratios), 4) if adoption_ratios else None
    ai_task_completion_rate = round(len(draft_saved) / len(draft_shown), 4) if draft_shown else None
    l6_completion_rate = round(step5_count / step1_count, 4) if step1_count else None
    path_click_rate = round(clicked_paths / len(suggest_success), 4) if suggest_success else None
    agent_median_rounds = median(session_max_rounds) if session_max_rounds else None

    def verdict(value: float | None, threshold: float, op: str) -> str:
        if value is None:
            return "待数据"
        if op == "gte":
            return "通过" if value >= threshold else "未达标"
        if op == "lte":
            return "通过" if value <= threshold else "未达标"
        return "—"

    kpis = [
        {
            "key": "ai_adoption_rate",
            "label": "AI 输出采纳率",
            "value": ai_adoption_rate,
            "threshold": "≥ 60%",
            "pass_line": 0.6,
            "verdict": verdict(ai_adoption_rate, 0.6, "gte"),
            "samples": len(adoption_ratios),
        },
        {
            "key": "ai_task_completion_rate",
            "label": "AI 任务完成率",
            "value": ai_task_completion_rate,
            "threshold": "≥ 40%",
            "pass_line": 0.4,
            "verdict": verdict(ai_task_completion_rate, 0.4, "gte"),
            "samples": len(draft_shown),
        },
        {
            "key": "l6_completion_rate",
            "label": "L6 任务完成率",
            "value": l6_completion_rate,
            "threshold": "≥ 70%",
            "pass_line": 0.7,
            "verdict": verdict(l6_completion_rate, 0.7, "gte"),
            "samples": step1_count,
        },
        {
            "key": "agent_path_click_rate",
            "label": "路径建议点击率",
            "value": path_click_rate,
            "threshold": "≥ 50%",
            "pass_line": 0.5,
            "verdict": verdict(path_click_rate, 0.5, "gte"),
            "samples": len(suggest_success),
        },
        {
            "key": "agent_median_rounds",
            "label": "助手中位轮次",
            "value": round(agent_median_rounds, 2) if agent_median_rounds is not None else None,
            "threshold": "≤ 2 轮",
            "pass_line": 2,
            "verdict": verdict(agent_median_rounds, 2, "lte"),
            "samples": len(session_max_rounds),
        },
    ]

    recent = [
        {
            "id": e.id,
            "event_name": e.event_name,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "job_id": e.job_id,
            "session_id": e.session_id,
            "properties": e.properties,
        }
        for e in events[:30]
    ]

    event_counts = {name: len(items) for name, items in sorted(by_name.items())}

    return {
        "period_days": days,
        "ledger_id": ledger_id,
        "generated_at": datetime.utcnow().isoformat(),
        "event_counts": event_counts,
        "total_events": len(events),
        "kpis": kpis,
        "recent_events": recent,
    }
