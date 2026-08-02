# -*- coding: utf-8 -*-
"""
模块功能：经济事件 summary 向量同步与相似推荐（E4）
业务场景：事件叙述写入 Qdrant，按账簿隔离检索相似历史事件
政策依据：向量结果仅作推荐，不替代人工判断与正式过账
输入数据：EconomicEvent（summary/title）
输出结果：同步结果、相似事件列表
创建日期：2026-08-02
更新记录：
    2026-08-02  E4 首版：upsert + ledger 隔离搜索
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import EconomicEvent
from app.services.doc_parsing.vector_store_service import safe_vector_store


class EconomicEventVectorService:
    """经济事件向量服务。"""

    SOURCE = "economic_event"

    def __init__(self, db: Session) -> None:
        self.db = db

    def event_text(self, event: EconomicEvent) -> str:
        """
        功能描述：拼事件语义文本。
        业务逻辑：标题 + 摘要 + 类型 + 状态，不含借贷金额主数据。
        """
        parts: list[str] = []
        if event.title:
            parts.append(f"标题:{event.title}")
        if event.summary:
            parts.append(f"摘要:{event.summary}")
        if event.event_type:
            parts.append(f"类型:{event.event_type}")
        if event.status:
            parts.append(f"状态:{event.status}")
        if event.event_no:
            parts.append(f"编号:{event.event_no}")
        return " ".join(parts)

    def point_id(self, event: EconomicEvent) -> str:
        return f"economic_event_{event.id}"

    def upsert_event(self, event: EconomicEvent) -> dict[str, Any]:
        """
        功能描述：将单个事件写入向量库。
        会计口径：payload 带 ledger_id，防止跨公司串库。
        """
        store = safe_vector_store()
        if not store:
            return {
                "vector_available": False,
                "synced": False,
                "message": "向量库当前不可用",
            }
        text = self.event_text(event)
        if not text.strip():
            return {
                "vector_available": True,
                "synced": False,
                "message": "事件缺少可向量化文本",
            }
        payload = {
            "ledger_id": event.ledger_id,
            "event_id": event.id,
            "event_no": event.event_no,
            "title": event.title,
            "event_type": event.event_type,
            "status": event.status,
            "source": self.SOURCE,
        }
        store.upsert_text(self.point_id(event), text, payload)
        return {
            "vector_available": True,
            "synced": True,
            "event_id": event.id,
            "point_id": self.point_id(event),
        }

    def sync_ledger_events(self, ledger_id: int, limit: int = 100) -> dict[str, Any]:
        """
        功能描述：批量同步某账簿事件到向量库。
        """
        rows = (
            self.db.query(EconomicEvent)
            .filter(EconomicEvent.ledger_id == ledger_id)
            .order_by(EconomicEvent.id.desc())
            .limit(max(1, min(limit, 500)))
            .all()
        )
        store = safe_vector_store()
        if not store:
            return {
                "vector_available": False,
                "synced_count": 0,
                "total": len(rows),
                "message": "向量库当前不可用",
            }
        synced = 0
        failed = 0
        for event in rows:
            try:
                result = self.upsert_event(event)
                if result.get("synced"):
                    synced += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
        return {
            "vector_available": True,
            "synced_count": synced,
            "failed_count": failed,
            "total": len(rows),
            "ledger_id": ledger_id,
        }

    def search_similar(
        self,
        *,
        ledger_id: int,
        query_text: str,
        limit: int = 5,
        exclude_event_id: int | None = None,
    ) -> dict[str, Any]:
        """
        功能描述：按自然语言检索本账簿相似事件。
        业务逻辑：强制 ledger_id；二次过滤 payload；排除自身。
        """
        store = safe_vector_store()
        if not store:
            return {
                "vector_available": False,
                "results": [],
                "message": "向量库当前不可用",
            }
        if ledger_id is None:
            return {
                "vector_available": True,
                "results": [],
                "message": "缺少 ledger_id，已拒绝跨账簿向量检索",
            }
        clean_query = (query_text or "").strip()
        if not clean_query:
            return {
                "vector_available": True,
                "results": [],
                "message": "查询文本为空",
            }

        filter_payload = {"ledger_id": ledger_id, "source": self.SOURCE}
        raw = store.search(clean_query, limit=limit * 3, filter_payload=filter_payload)
        results: list[dict[str, Any]] = []
        for item in raw:
            payload = item.get("payload") or {}
            if payload.get("ledger_id") != ledger_id:
                continue
            if payload.get("source") != self.SOURCE:
                continue
            event_id = payload.get("event_id")
            if exclude_event_id is not None and event_id == exclude_event_id:
                continue
            event = self.db.get(EconomicEvent, event_id) if event_id else None
            if event is None or event.ledger_id != ledger_id:
                continue
            results.append({
                "event_id": event.id,
                "event_no": event.event_no,
                "title": event.title,
                "event_type": event.event_type,
                "status": event.status,
                "summary": event.summary,
                "score": item.get("score"),
                "ledger_id": ledger_id,
            })
            if len(results) >= limit:
                break
        return {
            "vector_available": True,
            "query": clean_query,
            "ledger_id": ledger_id,
            "results": results,
        }
