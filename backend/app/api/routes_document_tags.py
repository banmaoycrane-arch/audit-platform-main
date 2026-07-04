# -*- coding: utf-8 -*-
"""
DocumentTag API 路由。

提供文档标签的增删改查、批量创建、统计信息等 RESTful 接口。
"""
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.doc_parsing.document_tag_service import (
    batch_assign_tags_to_documents,
    batch_delete_document_tags,
    batch_update_document_tags,
    create_document_tag,
    create_document_tags_batch,
    delete_document_tag,
    delete_document_tags_by_document,
    get_document_tag_by_id,
    get_document_tag_stats,
    list_document_tag_history,
    list_document_tags,
    update_document_tag,
)
from app.services.doc_parsing.document_tag_indexer import DocumentTagIndexer
from app.services.doc_parsing.document_tag_vector_service import DocumentTagVectorService

router = APIRouter(prefix="/api/document-tags", tags=["document-tags"])


class DocumentTagCreate(BaseModel):
    document_id: int
    document_type: str = Field(..., min_length=1, max_length=50)
    tag: str = Field(..., min_length=1, max_length=500)
    tag_type: str = Field(..., min_length=1, max_length=50)
    confidence: float = 0.8
    source: str = "rule"


class DocumentTagUpdate(BaseModel):
    tag: str | None = None
    tag_type: str | None = None
    confidence: float | None = None
    source: str | None = None


class DocumentTagBatchCreate(BaseModel):
    document_id: int
    document_type: str = Field(..., min_length=1, max_length=50)
    tags: list[dict[str, Any]]


class TagGenerateRequest(BaseModel):
    document_id: int
    document_type: str = Field(..., min_length=1, max_length=50)
    parsed_data: dict[str, Any]
    source: str = "rule"


class TagGenerateAIRequest(BaseModel):
    document_id: int
    document_type: str = Field(..., min_length=1, max_length=50)
    extracted_text: str
    parsed_data: dict[str, Any] | None = None


class TagGenerateHybridRequest(BaseModel):
    document_id: int
    document_type: str = Field(..., min_length=1, max_length=50)
    extracted_text: str
    parsed_data: dict[str, Any]
    ai_enabled: bool = True


@router.get("/{tag_id}", response_model=dict)
def get_document_tag(tag_id: int, db: Session = Depends(get_db)) -> Any:
    tag = get_document_tag_by_id(db, tag_id)
    if tag is None:
        raise HTTPException(status_code=404, detail="标签不存在")
    return tag.__dict__


@router.get("", response_model=list[dict[str, Any]])
def list_document_tags_api(
    document_id: int | None = None,
    document_type: str | None = None,
    tag_type: str | None = None,
    source: str | None = None,
    vector_stored: bool | None = None,
    created_from: str | None = None,
    created_to: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    created_from_dt = datetime.fromisoformat(created_from) if created_from else None
    created_to_dt = datetime.fromisoformat(created_to) if created_to else None
    tags = list_document_tags(
        db=db,
        document_id=document_id,
        document_type=document_type,
        tag_type=tag_type,
        source=source,
        vector_stored=vector_stored,
        created_from=created_from_dt,
        created_to=created_to_dt,
    )
    return [tag.__dict__ for tag in tags]


@router.post("", response_model=dict)
def create_document_tag_api(data: DocumentTagCreate, db: Session = Depends(get_db)) -> Any:
    try:
        tag = create_document_tag(
            db=db,
            document_id=data.document_id,
            document_type=data.document_type,
            tag=data.tag,
            tag_type=data.tag_type,
            confidence=data.confidence,
            source=data.source,
        )
        return tag.__dict__
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/batch", response_model=list[dict[str, Any]])
def create_document_tags_batch_api(data: DocumentTagBatchCreate, db: Session = Depends(get_db)) -> Any:
    tags = create_document_tags_batch(
        db=db,
        document_id=data.document_id,
        document_type=data.document_type,
        tags=data.tags,
    )
    return [tag.__dict__ for tag in tags]


@router.put("/{tag_id}", response_model=dict)
def update_document_tag_api(tag_id: int, data: DocumentTagUpdate, db: Session = Depends(get_db)) -> Any:
    try:
        tag = update_document_tag(
            db=db,
            document_tag_id=tag_id,
            tag=data.tag,
            tag_type=data.tag_type,
            confidence=data.confidence,
            source=data.source,
        )
        if tag is None:
            raise HTTPException(status_code=404, detail="标签不存在")
        return tag.__dict__
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{tag_id}", response_model=dict)
def delete_document_tag_api(tag_id: int, db: Session = Depends(get_db)) -> Any:
    success = delete_document_tag(db, tag_id)
    if not success:
        raise HTTPException(status_code=404, detail="标签不存在")
    return {"success": True}


@router.delete("/document/{document_id}", response_model=dict)
def delete_document_tags_by_document_api(document_id: int, db: Session = Depends(get_db)) -> Any:
    count = delete_document_tags_by_document(db, document_id)
    return {"success": True, "deleted_count": count}


@router.post("/generate", response_model=list[dict[str, Any]])
def generate_document_tags_api(data: TagGenerateRequest, db: Session = Depends(get_db)) -> Any:
    indexer = DocumentTagIndexer(db)
    tags = indexer.generate_tags_from_parsed_data(
        document_id=data.document_id,
        document_type=data.document_type,
        parsed_data=data.parsed_data,
        source=data.source,
    )
    return [tag.__dict__ for tag in tags]


@router.post("/generate/ai", response_model=list[dict[str, Any]])
def generate_document_tags_ai_api(data: TagGenerateAIRequest, db: Session = Depends(get_db)) -> Any:
    indexer = DocumentTagIndexer(db)
    tags = indexer.generate_tags_with_ai(
        document_id=data.document_id,
        document_type=data.document_type,
        extracted_text=data.extracted_text,
        parsed_data=data.parsed_data,
    )
    return [tag.__dict__ for tag in tags]


@router.post("/generate/hybrid", response_model=list[dict[str, Any]])
def generate_document_tags_hybrid_api(data: TagGenerateHybridRequest, db: Session = Depends(get_db)) -> Any:
    indexer = DocumentTagIndexer(db)
    tags = indexer.generate_tags_hybrid(
        document_id=data.document_id,
        document_type=data.document_type,
        extracted_text=data.extracted_text,
        parsed_data=data.parsed_data,
        ai_enabled=data.ai_enabled,
    )
    return [tag.__dict__ for tag in tags]


@router.get("/stats", response_model=dict)
def get_document_tag_stats_api(document_type: str | None = None, db: Session = Depends(get_db)) -> Any:
    return get_document_tag_stats(db, document_type)


@router.post("/sync-vectors", response_model=dict)
def sync_pending_tags_api(db: Session = Depends(get_db)) -> Any:
    vector_service = DocumentTagVectorService(db)
    count = vector_service.sync_pending_tags()
    return {"success": True, "synced_count": count}


@router.post("/search", response_model=list[dict[str, Any]])
def search_similar_tags_api(query_text: str, document_type: str | None = None, tag_type: str | None = None, limit: int = 10, db: Session = Depends(get_db)) -> Any:
    vector_service = DocumentTagVectorService(db)
    results = vector_service.search_similar_tags(
        query_text=query_text,
        document_type=document_type,
        tag_type=tag_type,
        limit=limit,
    )
    return results


class BatchUpdateRequest(BaseModel):
    tag_ids: list[int]
    updates: dict[str, Any]
    operator: str | None = None
    reason: str | None = None


class BatchDeleteRequest(BaseModel):
    tag_ids: list[int]
    operator: str | None = None
    reason: str | None = None


class BatchAssignRequest(BaseModel):
    document_ids: list[int]
    document_type: str = Field(..., min_length=1, max_length=50)
    tags: list[dict[str, Any]]


@router.get("/history", response_model=list[dict[str, Any]])
def list_tag_history_api(
    document_tag_id: int | None = None,
    document_id: int | None = None,
    action: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> Any:
    history = list_document_tag_history(
        db=db,
        document_tag_id=document_tag_id,
        document_id=document_id,
        action=action,
        limit=limit,
    )
    return [h.__dict__ for h in history]


@router.put("/batch", response_model=dict)
def batch_update_tags_api(data: BatchUpdateRequest, db: Session = Depends(get_db)) -> Any:
    try:
        count = batch_update_document_tags(
            db=db,
            tag_ids=data.tag_ids,
            updates=data.updates,
            operator=data.operator,
            reason=data.reason,
        )
        return {"success": True, "updated_count": count}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/batch", response_model=dict)
def batch_delete_tags_api(data: BatchDeleteRequest, db: Session = Depends(get_db)) -> Any:
    count = batch_delete_document_tags(
        db=db,
        tag_ids=data.tag_ids,
        operator=data.operator,
        reason=data.reason,
    )
    return {"success": True, "deleted_count": count}


@router.post("/batch/assign", response_model=dict)
def batch_assign_tags_api(data: BatchAssignRequest, db: Session = Depends(get_db)) -> Any:
    try:
        count = batch_assign_tags_to_documents(
            db=db,
            document_ids=data.document_ids,
            document_type=data.document_type,
            tags=data.tags,
        )
        return {"success": True, "created_count": count}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))