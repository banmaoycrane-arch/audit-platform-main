from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session
from typing import Any, Optional

from app.db.models import Transaction, TransactionOperation
from app.db.session import get_db
from app.services.shared.transaction_manager import TransactionManager

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _serialize_transaction(tx: Transaction) -> dict[str, Any]:
    return {
        "id": tx.id,
        "transaction_id": tx.transaction_id,
        "transaction_type": tx.transaction_type,
        "context_type": tx.context_type,
        "context_id": tx.context_id,
        "status": tx.status,
        "operation_count": tx.operation_count,
        "succeeded_count": tx.succeeded_count,
        "failed_count": tx.failed_count,
        "started_at": tx.started_at.isoformat() if tx.started_at else None,
        "committed_at": tx.committed_at.isoformat() if tx.committed_at else None,
        "rolled_back_at": tx.rolled_back_at.isoformat() if tx.rolled_back_at else None,
        "error_message": tx.error_message,
    }


def _serialize_operation(op: TransactionOperation) -> dict[str, Any]:
    return {
        "id": op.id,
        "operation_order": op.operation_order,
        "operation_type": op.operation_type,
        "entity_type": op.entity_type,
        "entity_id": op.entity_id,
        "status": op.status,
        "error_message": op.error_message,
        "completed_at": op.completed_at.isoformat() if op.completed_at else None,
    }


@router.get("/summary")
def get_transactions_summary(
    context_type: Optional[str] = Query(None),
    context_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """按状态统计事务数量。"""
    query = db.query(Transaction.status, func.count(Transaction.id))
    if context_type is not None:
        query = query.filter(Transaction.context_type == context_type)
    if context_id is not None:
        query = query.filter(Transaction.context_id == context_id)

    counts = {"pending": 0, "committed": 0, "rolled_back": 0, "failed": 0}
    total = 0
    for status, cnt in query.group_by(Transaction.status).all():
        if status in counts:
            counts[status] = cnt
        total += cnt
    counts["total"] = total
    return counts


@router.get("/")
def list_transactions(
    context_type: Optional[str] = Query(None),
    context_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """列出事务。"""
    query = db.query(Transaction)
    if context_type is not None:
        query = query.filter(Transaction.context_type == context_type)
    if context_id is not None:
        query = query.filter(Transaction.context_id == context_id)
    if status is not None:
        query = query.filter(Transaction.status == status)
    transactions = (
        query.order_by(Transaction.started_at.desc()).limit(limit).all()
    )
    return [_serialize_transaction(tx) for tx in transactions]


@router.get("/{transaction_id}")
def get_transaction_detail(
    transaction_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """事务详情，含 operations 摘要。"""
    tx = db.get(Transaction, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="事务不存在")
    data = _serialize_transaction(tx)
    data["summary"] = {
        "operation_count": tx.operation_count,
        "succeeded_count": tx.succeeded_count,
        "failed_count": tx.failed_count,
    }
    return data


@router.get("/{transaction_id}/operations")
def get_transaction_operations(
    transaction_id: int,
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """事务操作列表。"""
    tx = db.get(Transaction, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="事务不存在")
    manager = TransactionManager(db)
    operations = manager.get_transaction_operations(transaction_id)
    return [_serialize_operation(op) for op in operations]


@router.post("/{transaction_id}/rollback")
def rollback_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """手动回滚 pending 事务。"""
    tx = db.get(Transaction, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="事务不存在")
    if tx.status != "pending":
        raise HTTPException(
            status_code=400,
            detail=f"仅 pending 事务可以手动回滚，当前状态：{tx.status}",
        )
    manager = TransactionManager(db)
    manager.rollback_transaction(transaction_id, error_message="manual rollback")
    db.refresh(tx)
    return {
        "transaction_id": tx.id,
        "status": tx.status,
        "message": "事务已回滚",
    }
