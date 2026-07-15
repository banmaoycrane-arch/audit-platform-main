# -*- coding: utf-8 -*-
"""税务城市出口 IP 池：绑定、故障轮换、种子数据。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import (
    TaxCityEgressPool,
    TaxEgressBinding,
    TaxEgressNode,
    TaxRotationEvent,
)

DEFAULT_CITY_SEEDS: list[dict[str, Any]] = [
    {
        "city_code": "330100",
        "city_name": "杭州市",
        "bureau_province": "浙江省",
        "nodes": [
            {
                "node_key": "hz-partner-1",
                "egress_ip": "0.0.0.0",
                "provider": "合作商IP池-杭州（请替换为真实出口IP）",
                "worker_host": "partner-proxy-hz:port",
                "max_tenants": 5,
                "health_score": 1.0,
            },
        ],
    },
    {
        "city_code": "440300",
        "city_name": "深圳市",
        "bureau_province": "广东省",
        "nodes": [
            {
                "node_key": "sz-partner-1",
                "egress_ip": "0.0.0.0",
                "provider": "合作商IP池-深圳（请替换为真实出口IP）",
                "worker_host": "partner-proxy-sz:port",
                "max_tenants": 5,
                "health_score": 1.0,
            },
        ],
    },
    {
        "city_code": "140100",
        "city_name": "太原市",
        "bureau_province": "山西省",
        "nodes": [
            {
                "node_key": "sx-partner-1",
                "egress_ip": "0.0.0.0",
                "provider": "合作商IP池-山西太原（请替换为真实出口IP）",
                "worker_host": "partner-proxy-sx:port",
                "max_tenants": 5,
                "health_score": 1.0,
            },
        ],
    },
]


def ensure_default_pools(db: Session) -> None:
    settings = get_settings()
    if not settings.tax_egress_seed_enabled:
        return
    existing = db.scalar(select(TaxCityEgressPool.id).limit(1))
    if existing is not None:
        return
    for city in DEFAULT_CITY_SEEDS:
        pool = TaxCityEgressPool(
            city_code=city["city_code"],
            city_name=city["city_name"],
            bureau_province=city["bureau_province"],
            pool_policy="sticky_with_failover",
            max_rotate_per_taxpayer_7d=settings.tax_egress_max_rotate_per_taxpayer_7d,
            cooling_hours=settings.tax_egress_cooling_hours,
        )
        db.add(pool)
        db.flush()
        for node in city["nodes"]:
            db.add(
                TaxEgressNode(
                    pool_id=pool.id,
                    node_key=node["node_key"],
                    egress_ip=node["egress_ip"],
                    provider=node.get("provider"),
                    status=node.get("status", "active"),
                    max_tenants=node.get("max_tenants", 5),
                    health_score=node.get("health_score", 1.0),
                    last_health_at=datetime.utcnow(),
                )
            )
    db.commit()


def _node_dict(node: TaxEgressNode) -> dict[str, Any]:
    return {
        "id": node.id,
        "node_key": node.node_key,
        "egress_ip": node.egress_ip,
        "provider": node.provider,
        "worker_host": node.worker_host,
        "status": node.status,
        "load": node.current_bindings,
        "max_tenants": node.max_tenants,
        "health_score": node.health_score,
        "last_health_at": node.last_health_at.isoformat() if node.last_health_at else None,
    }


def get_pool_overview(db: Session, city_code: str | None = None) -> dict[str, Any]:
    ensure_default_pools(db)
    pools = db.scalars(select(TaxCityEgressPool).order_by(TaxCityEgressPool.city_code)).all()
    if city_code:
        pools = [p for p in pools if p.city_code == city_code]
    cities = []
    for pool in pools:
        nodes = db.scalars(
            select(TaxEgressNode).where(TaxEgressNode.pool_id == pool.id).order_by(TaxEgressNode.id)
        ).all()
        active = sum(1 for n in nodes if n.status == "active")
        slots = sum(max(0, n.max_tenants - n.current_bindings) for n in nodes if n.status == "active")
        cities.append(
            {
                "city_code": pool.city_code,
                "city_name": pool.city_name,
                "bureau_province": pool.bureau_province,
                "pool_policy": pool.pool_policy,
                "max_rotate_per_taxpayer_7d": pool.max_rotate_per_taxpayer_7d,
                "cooling_hours": pool.cooling_hours,
                "stats": {"active_nodes": active, "total_nodes": len(nodes), "remaining_slots": slots},
                "nodes": [_node_dict(n) for n in nodes],
            }
        )
    settings = get_settings()
    return {
        "pool_policy": "sticky_with_failover",
        "config": {
            "seed_enabled": settings.tax_egress_seed_enabled,
            "max_rotate_per_taxpayer_7d": settings.tax_egress_max_rotate_per_taxpayer_7d,
            "cooling_hours": settings.tax_egress_cooling_hours,
            "default_lease_days": settings.tax_egress_default_lease_days,
        },
        "cities": cities,
    }


def list_bindings(
    db: Session,
    *,
    ledger_id: int | None = None,
    city_code: str | None = None,
) -> list[dict[str, Any]]:
    ensure_default_pools(db)
    stmt = select(TaxEgressBinding).order_by(TaxEgressBinding.id)
    if ledger_id is not None:
        stmt = stmt.where(TaxEgressBinding.ledger_id == ledger_id)
    if city_code:
        stmt = stmt.where(TaxEgressBinding.city_code == city_code)
    bindings = db.scalars(stmt).all()
    pool_names = {
        p.city_code: p.city_name
        for p in db.scalars(select(TaxCityEgressPool)).all()
    }
    result: list[dict[str, Any]] = []
    for binding in bindings:
        node = db.get(TaxEgressNode, binding.egress_node_id)
        result.append(_binding_dict(binding, node, city_name=pool_names.get(binding.city_code)))
    return result


def _binding_dict(
    binding: TaxEgressBinding,
    node: TaxEgressNode | None,
    *,
    city_name: str | None = None,
) -> dict[str, Any]:
    return {
        "id": binding.id,
        "taxpayer_id": binding.taxpayer_id,
        "taxpayer_name": binding.taxpayer_name,
        "ledger_id": binding.ledger_id,
        "city_code": binding.city_code,
        "city_name": city_name or binding.city_code,
        "egress_ip": node.egress_ip if node else None,
        "node_id": node.id if node else None,
        "node_key": node.node_key if node else None,
        "lease_end": binding.lease_end.date().isoformat() if binding.lease_end else None,
        "rotate_count_7d": binding.rotate_count_7d,
        "binding_status": binding.binding_status,
        "session_state": binding.session_state,
    }


def _select_for_new_binding(db: Session, city_code: str) -> TaxEgressNode:
    pool = db.scalar(select(TaxCityEgressPool).where(TaxCityEgressPool.city_code == city_code))
    if pool is None:
        raise ValueError(f"城市池不存在: {city_code}")
    nodes = db.scalars(
        select(TaxEgressNode)
        .where(TaxEgressNode.pool_id == pool.id, TaxEgressNode.status == "active")
        .order_by(TaxEgressNode.current_bindings, TaxEgressNode.health_score.desc())
    ).all()
    candidates = [n for n in nodes if n.current_bindings < n.max_tenants]
    if not candidates:
        raise ValueError(f"城市 {city_code} 无可用出口槽位")
    return candidates[0]


def _select_failover(db: Session, city_code: str, exclude_node_ids: set[int]) -> TaxEgressNode:
    pool = db.scalar(select(TaxCityEgressPool).where(TaxCityEgressPool.city_code == city_code))
    if pool is None:
        raise ValueError(f"城市池不存在: {city_code}")
    nodes = db.scalars(select(TaxEgressNode).where(TaxEgressNode.pool_id == pool.id, TaxEgressNode.status == "active")).all()
    candidates = [
        n for n in nodes
        if n.current_bindings < n.max_tenants and n.id not in exclude_node_ids
    ]
    if not candidates:
        raise ValueError(f"城市 {city_code} 无故障转移目标")
    return min(candidates, key=lambda n: n.current_bindings)


def create_binding(
    db: Session,
    *,
    taxpayer_id: str,
    taxpayer_name: str,
    city_code: str,
    ledger_id: int | None,
    team_id: int | None,
) -> dict[str, Any]:
    ensure_default_pools(db)
    existing = db.scalar(select(TaxEgressBinding).where(TaxEgressBinding.taxpayer_id == taxpayer_id))
    if existing is not None:
        node = db.get(TaxEgressNode, existing.egress_node_id)
        return _binding_dict(existing, node)
    node = _select_for_new_binding(db, city_code)
    settings = get_settings()
    now = datetime.utcnow()
    binding = TaxEgressBinding(
        taxpayer_id=taxpayer_id.strip(),
        taxpayer_name=taxpayer_name.strip(),
        ledger_id=ledger_id,
        team_id=team_id,
        city_code=city_code,
        egress_node_id=node.id,
        lease_start=now,
        lease_end=now + timedelta(days=settings.tax_egress_default_lease_days),
    )
    node.current_bindings += 1
    db.add(binding)
    db.flush()
    db.add(
        TaxRotationEvent(
            taxpayer_id=binding.taxpayer_id,
            binding_id=binding.id,
            old_node_id=None,
            new_node_id=node.id,
            old_egress_ip=None,
            new_egress_ip=node.egress_ip,
            trigger_code="new_binding",
            reason_detail="weighted_round_robin 首次绑定",
            created_by="system",
        )
    )
    db.commit()
    db.refresh(binding)
    return _binding_dict(binding, node)


def rotate_binding(
    db: Session,
    binding_id: int,
    *,
    trigger_code: str = "T5_manual_admin",
    reason_detail: str | None = None,
    created_by: str = "user",
) -> dict[str, Any]:
    settings = get_settings()
    binding = db.get(TaxEgressBinding, binding_id)
    if binding is None:
        raise ValueError("绑定不存在")
    if binding.rotate_count_7d >= settings.tax_egress_max_rotate_per_taxpayer_7d and trigger_code != "T5_manual_admin":
        raise ValueError("7 日内自动轮换次数已达上限，请人工处理")
    old_node = db.get(TaxEgressNode, binding.egress_node_id)
    if old_node is None:
        raise ValueError("当前节点不存在")
    exclude = {old_node.id}
    new_node = _select_failover(db, binding.city_code, exclude)
    now = datetime.utcnow()
    old_node.current_bindings = max(0, old_node.current_bindings - 1)
    old_node.status = "cooling"
    old_node.cooling_until = now + timedelta(hours=settings.tax_egress_cooling_hours)
    new_node.current_bindings += 1
    binding.egress_node_id = new_node.id
    binding.rotate_count_7d += 1
    binding.last_rotate_at = now
    binding.binding_status = "need_reauth"
    binding.session_state = "need_qr"
    db.add(
        TaxRotationEvent(
            taxpayer_id=binding.taxpayer_id,
            binding_id=binding.id,
            old_node_id=old_node.id,
            new_node_id=new_node.id,
            old_egress_ip=old_node.egress_ip,
            new_egress_ip=new_node.egress_ip,
            trigger_code=trigger_code,
            reason_detail=reason_detail or "池内故障转移",
            created_by=created_by,
        )
    )
    db.commit()
    db.refresh(binding)
    return _binding_dict(binding, new_node)


def start_tax_session(db: Session, binding_id: int) -> dict[str, Any]:
    binding = db.get(TaxEgressBinding, binding_id)
    if binding is None:
        raise ValueError("绑定不存在")
    node = db.get(TaxEgressNode, binding.egress_node_id)
    binding.session_state = "need_qr"
    binding.binding_status = "need_reauth"
    db.commit()
    return {
        "binding_id": binding.id,
        "session_state": binding.session_state,
        "egress_ip": node.egress_ip if node else None,
        "message": "请在对应地区 Worker 完成税局扫码登录（Phase 1 未接真实税局）",
    }


def list_rotation_events(db: Session, *, limit: int = 30) -> list[dict[str, Any]]:
    events = db.scalars(
        select(TaxRotationEvent).order_by(TaxRotationEvent.created_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": e.id,
            "time": e.created_at.isoformat(sep=" ", timespec="minutes") if e.created_at else None,
            "taxpayer_id": e.taxpayer_id,
            "old_ip": e.old_egress_ip or "—",
            "new_ip": e.new_egress_ip,
            "trigger": e.trigger_code,
            "detail": e.reason_detail,
            "created_by": e.created_by,
        }
        for e in events
    ]
