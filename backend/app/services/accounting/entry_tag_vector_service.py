# -*- coding: utf-8 -*-
"""
分录标签向量服务（EntryTag Vector Service）。

业务场景：
    将 EntryTag 及其关联的凭证语义信息写入 Qdrant 向量数据库，
    支持自然语言查询快速定位相关标签及关联凭证数据。

政策依据：
    向量检索结果仅用于尽调、审计风险识别和语义关联，
    不替代确定性会计计算与报表生成。

输入数据：
    - EntryTag 对象
    - 关联 AccountingEntry 对象

输出结果：
    - 向量库 upsert 结果
    - 自然语言检索结果
"""
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AccountingEntry, EntryTag
from app.services.doc_parsing.vector_store_service import safe_vector_store


class EntryTagVectorService:
    def __init__(self, db: Session):
        self.db = db

    def tag_text(self, tag: EntryTag, entry: AccountingEntry | None) -> str:
        """
        生成标签语义文本。

        文本包含维度分类、标签值、展示名、摘要、科目、往来单位、金额、日期等，
        用于向量编码和自然语言检索。
        """
        parts: list[str] = []

        if tag.category and tag.category.code:
            parts.append(f"维度:{tag.category.code}")
            parts.append(f"维度名:{tag.category.name or tag.category.code}")
        elif tag.tag_type:
            parts.append(f"维度:{tag.tag_type}")

        if tag.tag_value:
            parts.append(f"标签值:{tag.tag_value}")
        if tag.display_name:
            parts.append(f"展示名:{tag.display_name}")

        if entry:
            if entry.summary:
                parts.append(f"摘要:{entry.summary}")
            if entry.account_code:
                parts.append(f"科目:{entry.account_code}")
            if entry.account_name:
                parts.append(f"科目名:{entry.account_name}")
            if entry.counterparty:
                parts.append(f"往来单位:{entry.counterparty}")
            if entry.voucher_date:
                parts.append(f"日期:{entry.voucher_date.isoformat()}")
            amount = entry.debit_amount or entry.credit_amount or 0
            if amount:
                parts.append(f"金额:{amount}")
            if entry.voucher_no:
                parts.append(f"凭证号:{entry.voucher_no}")

        return " ".join(parts)

    def point_id(self, tag: EntryTag) -> str:
        return f"entry_tag_{tag.id}"

    def sync_pending(self, limit: int = 100) -> dict[str, Any]:
        """
        同步待处理标签到向量库。
        """
        store = safe_vector_store()
        pending = (
            self.db.query(EntryTag)
            .filter(EntryTag.vector_pending == True)
            .limit(limit)
            .all()
        )
        if not store:
            return {
                "vector_available": False,
                "synced_count": 0,
                "pending_count": len(pending),
                "message": "向量库当前不可用",
            }

        synced_count = 0
        failed_count = 0
        for tag in pending:
            entry = self.db.get(AccountingEntry, tag.entry_id)
            text = self.tag_text(tag, entry)
            payload = {
                "entry_id": tag.entry_id,
                "tag_id": tag.id,
                "category_code": tag.category.code if tag.category else tag.tag_type,
                "category_name": tag.category.name if tag.category else None,
                "tag_value": tag.tag_value,
                "display_name": tag.display_name,
                "tag_source": tag.tag_source,
                "source": "entry_tag",
            }
            try:
                store.upsert_text(self.point_id(tag), text, payload)
                tag.vector_pending = False
                synced_count += 1
            except Exception:
                failed_count += 1
        self.db.commit()
        return {
            "vector_available": True,
            "synced_count": synced_count,
            "pending_count": failed_count,
            "failed_count": failed_count,
        }

    def search(
        self,
        query_text: str,
        limit: int = 10,
        category_code: str | None = None,
    ) -> dict[str, Any]:
        """
        自然语言检索标签及关联凭证。

        Args:
            query_text: 自然语言查询文本
            limit: 返回结果数量
            category_code: 可选的维度分类过滤

        Returns:
            检索结果，包含相似度分数、标签信息、关联 entry_id
        """
        store = safe_vector_store()
        if not store:
            return {
                "vector_available": False,
                "results": [],
                "message": "向量库当前不可用",
            }

        try:
            raw_results = store.search(query_text, limit=limit * 2)
            results: list[dict[str, Any]] = []
            for item in raw_results:
                payload = item.get("payload") or {}
                if category_code and payload.get("category_code") != category_code:
                    continue

                entry_id = payload.get("entry_id")
                entry = self.db.get(AccountingEntry, entry_id) if entry_id else None
                results.append({
                    "tag_id": payload.get("tag_id"),
                    "entry_id": entry_id,
                    "category_code": payload.get("category_code"),
                    "category_name": payload.get("category_name"),
                    "tag_value": payload.get("tag_value"),
                    "display_name": payload.get("display_name"),
                    "score": item.get("score"),
                    "voucher_no": entry.voucher_no if entry else None,
                    "voucher_date": str(entry.voucher_date) if entry and entry.voucher_date else None,
                    "account_code": entry.account_code if entry else None,
                    "summary": entry.summary if entry else None,
                })
                if len(results) >= limit:
                    break

            return {
                "vector_available": True,
                "query": query_text,
                "results": results,
            }
        except Exception as e:
            return {
                "vector_available": True,
                "results": [],
                "message": f"检索失败：{e}",
            }
