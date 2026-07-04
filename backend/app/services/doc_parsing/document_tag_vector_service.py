# -*- coding: utf-8 -*-
"""
文档标签向量服务（DocumentTag Vector Service）。

业务场景：
    将 DocumentTag 及其关联的文档语义信息写入 Qdrant 向量数据库，
    支持自然语言查询快速定位相关文档及标签数据。

政策依据：
    向量检索结果仅用于尽调、审计风险识别和语义关联，
    不替代确定性会计计算与报表生成。

输入数据：
    - DocumentTag 对象
    - 关联文档数据

输出结果：
    - 向量库 upsert 结果
    - 自然语言检索结果
"""
from typing import Any

from sqlalchemy.orm import Session
from qdrant_client.http import models as qmodels

from app.db.models import DocumentTag
from app.services.doc_parsing.vector_store_service import safe_vector_store


class DocumentTagVectorService:
    """
    文档标签向量服务，负责文档标签的向量编码与检索。
    """

    def __init__(self, db: Session):
        self.db = db
        self.vector_store = safe_vector_store()
        self.collection_name = "document_tags"

    def tag_text(self, tag: DocumentTag) -> str:
        """
        生成标签语义文本。

        文本包含文档类型、标签值、标签类型、置信度、来源等，
        用于向量编码和自然语言检索。
        """
        parts: list[str] = []

        parts.append(f"文档类型:{tag.document_type}")
        parts.append(f"标签类型:{tag.tag_type}")
        parts.append(f"标签值:{tag.tag}")
        parts.append(f"置信度:{tag.confidence}")
        parts.append(f"来源:{tag.source}")

        return " ".join(parts)

    def sync_tag_to_vector(self, tag: DocumentTag) -> bool:
        """
        将单个标签同步到向量数据库。

        Returns:
            bool: 是否同步成功
        """
        if not self.vector_store:
            return False

        try:
            text = self.tag_text(tag)
            self.vector_store.upsert_text(
                point_id=f"doc_tag_{tag.id}",
                text=text,
                payload={
                    "tag_id": tag.id,
                    "document_id": tag.document_id,
                    "document_type": tag.document_type,
                    "tag": tag.tag,
                    "tag_type": tag.tag_type,
                    "confidence": tag.confidence,
                    "source": tag.source,
                },
            )
            tag.vector_id = f"doc_tag_{tag.id}"
            tag.vector_stored = True
            self.db.flush()
            return True
        except Exception:
            return False

    def sync_pending_tags(self, batch_size: int = 50) -> int:
        """
        同步所有待同步的标签到向量数据库。

        Args:
            batch_size: 每批处理数量

        Returns:
            int: 成功同步的标签数量
        """
        if not self.vector_store:
            return 0

        pending_tags = (
            self.db.query(DocumentTag)
            .filter(DocumentTag.vector_stored == False)
            .limit(batch_size)
            .all()
        )

        success_count = 0
        for tag in pending_tags:
            if self.sync_tag_to_vector(tag):
                success_count += 1

        return success_count

    def search_similar_tags(
        self,
        query_text: str,
        document_type: str | None = None,
        tag_type: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """
        通过自然语言查询相似标签。

        Args:
            query_text: 查询文本
            document_type: 文档类型过滤
            tag_type: 标签类型过滤
            limit: 返回数量限制

        Returns:
            list[dict]: 相似标签列表，包含标签信息和相似度
        """
        if not self.vector_store:
            return []

        results = self.vector_store.search(
            text=query_text,
            limit=limit,
        )

        filtered_results = []
        for result in results:
            payload = result.get("payload", {})
            if document_type and payload.get("document_type") != document_type:
                continue
            if tag_type and payload.get("tag_type") != tag_type:
                continue
            filtered_results.append(result)

        return filtered_results

    def delete_tag_from_vector(self, tag: DocumentTag) -> bool:
        """
        从向量数据库删除标签。

        Returns:
            bool: 是否删除成功
        """
        if not self.vector_store or not tag.vector_id:
            return False

        try:
            self.vector_store.client.delete(
                collection_name=self.vector_store.collection,
                points_selector=qmodels.PointIdsList(
                    points=[tag.vector_id]
                ),
            )
            tag.vector_id = None
            tag.vector_stored = False
            self.db.flush()
            return True
        except Exception:
            return False
