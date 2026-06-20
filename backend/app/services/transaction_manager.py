import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable, Type
from sqlalchemy.orm import Session
from contextlib import contextmanager

from app.db.models import (
    Transaction, TransactionOperation, TransactionCheckpoint,
    AccountingEntry, Contract, Invoice, InventoryDocument, BankStatement,
    SourceFile, ImportJob
)

# 实体类型到模型类的映射
ENTITY_MODEL_MAP = {
    "accounting_entry": AccountingEntry,
    "contract": Contract,
    "invoice": Invoice,
    "inventory_document": InventoryDocument,
    "bank_statement": BankStatement,
    "source_file": SourceFile,
    "import_job": ImportJob,
}


class TransactionManager:
    def __init__(self, db: Session):
        self.db = db
        self.current_transaction = None

    @contextmanager
    def begin_transaction(self, transaction_type: str, context_id: Optional[int] = None, 
                          context_type: Optional[str] = None):
        """开始一个事务"""
        transaction_id = str(uuid.uuid4())
        
        transaction = Transaction(
            transaction_id=transaction_id,
            transaction_type=transaction_type,
            context_id=context_id,
            context_type=context_type,
            status="pending"
        )
        self.db.add(transaction)
        self.db.flush()
        
        self.current_transaction = transaction
        
        try:
            yield transaction
            self.commit_transaction(transaction.id)
        except Exception as e:
            self.rollback_transaction(transaction.id, str(e))
            raise
        finally:
            self.current_transaction = None

    def commit_transaction(self, transaction_id: int):
        """提交事务"""
        transaction = self._get_transaction(transaction_id)
        if transaction:
            transaction.status = "committed"
            transaction.committed_at = datetime.utcnow()
            self.db.commit()

    def rollback_transaction(self, transaction_id: int, error_message: str = ""):
        """回滚事务"""
        transaction = self._get_transaction(transaction_id)
        if not transaction:
            return
        
        try:
            # 获取所有已成功的操作并按逆序回滚
            operations = self.db.query(TransactionOperation)\
                .filter(TransactionOperation.transaction_id == transaction_id)\
                .filter(TransactionOperation.status == "succeeded")\
                .order_by(TransactionOperation.operation_order.desc())\
                .all()
            
            for op in operations:
                self._rollback_operation(op)
                op.status = "rolled_back"
            
            transaction.status = "rolled_back"
            transaction.rolled_back_at = datetime.utcnow()
            transaction.error_message = error_message
            self.db.commit()
        except Exception as e:
            transaction.status = "failed"
            transaction.error_message = f"Rollback failed: {str(e)}"
            self.db.commit()

    def _rollback_operation(self, operation: TransactionOperation):
        """回滚单个操作"""
        if operation.rollback_details:
            entity_type = operation.entity_type
            entity_id = operation.entity_id
            
            if operation.operation_type == "create" and entity_id:
                # 删除创建的记录
                self._delete_entity(entity_type, entity_id)
            elif operation.operation_type == "update" and entity_id:
                # 恢复到更新前的状态
                self._restore_entity(entity_type, entity_id, operation.rollback_details)
            elif operation.operation_type == "delete" and operation.rollback_details:
                # 重新创建删除的记录
                self._restore_deleted_entity(entity_type, operation.rollback_details)

    def _get_entity_model(self, entity_type: str) -> Optional[Type]:
        """根据实体类型获取对应的模型类"""
        return ENTITY_MODEL_MAP.get(entity_type)

    def _delete_entity(self, entity_type: str, entity_id: int):
        """删除实体"""
        model_class = self._get_entity_model(entity_type)
        if model_class:
            entity = self.db.query(model_class).filter(model_class.id == entity_id).first()
            if entity:
                self.db.delete(entity)
                self.db.flush()

    def _restore_entity(self, entity_type: str, entity_id: int, rollback_details: Dict):
        """恢复实体到之前的状态"""
        model_class = self._get_entity_model(entity_type)
        if model_class and rollback_details:
            entity = self.db.query(model_class).filter(model_class.id == entity_id).first()
            if entity:
                # 将实体恢复到更新前的状态
                for key, value in rollback_details.items():
                    if hasattr(entity, key):
                        setattr(entity, key, value)
                self.db.flush()

    def _restore_deleted_entity(self, entity_type: str, rollback_details: Dict):
        """重新创建删除的实体"""
        model_class = self._get_entity_model(entity_type)
        if model_class and rollback_details:
            # 从rollback_details中提取字段创建新实体
            entity_data = rollback_details.copy()
            # 移除id字段，让数据库自动生成
            entity_data.pop('id', None)
            entity_data.pop('created_at', None)
            entity_data.pop('updated_at', None)
            
            entity = model_class(**entity_data)
            self.db.add(entity)
            self.db.flush()

    def record_operation(self, transaction_id: int, operation_type: str, 
                         entity_type: str, operation_details: Dict,
                         rollback_details: Optional[Dict] = None) -> TransactionOperation:
        """记录操作"""
        transaction = self._get_transaction(transaction_id)
        if not transaction:
            raise ValueError("Transaction not found")
        
        operation_order = transaction.operation_count + 1
        
        operation = TransactionOperation(
            transaction_id=transaction_id,
            operation_order=operation_order,
            operation_type=operation_type,
            entity_type=entity_type,
            operation_details=operation_details,
            rollback_details=rollback_details
        )
        
        self.db.add(operation)
        transaction.operation_count = operation_order
        self.db.flush()
        
        return operation

    def mark_operation_success(self, operation_id: int, entity_id: int):
        """标记操作成功"""
        operation = self.db.query(TransactionOperation)\
            .filter(TransactionOperation.id == operation_id)\
            .first()
        
        if operation:
            operation.status = "succeeded"
            operation.entity_id = entity_id
            operation.completed_at = datetime.utcnow()
            
            transaction = self._get_transaction(operation.transaction_id)
            if transaction:
                transaction.succeeded_count += 1
            
            self.db.flush()

    def mark_operation_failure(self, operation_id: int, error_message: str):
        """标记操作失败"""
        operation = self.db.query(TransactionOperation)\
            .filter(TransactionOperation.id == operation_id)\
            .first()
        
        if operation:
            operation.status = "failed"
            operation.error_message = error_message
            operation.completed_at = datetime.utcnow()
            
            transaction = self._get_transaction(operation.transaction_id)
            if transaction:
                transaction.failed_count += 1
            
            self.db.flush()

    def add_checkpoint(self, transaction_id: int, checkpoint_name: str):
        """添加检查点"""
        transaction = self._get_transaction(transaction_id)
        if not transaction:
            raise ValueError("Transaction not found")
        
        checkpoint_count = self.db.query(TransactionCheckpoint)\
            .filter(TransactionCheckpoint.transaction_id == transaction_id)\
            .count()
        
        checkpoint = TransactionCheckpoint(
            transaction_id=transaction_id,
            checkpoint_name=checkpoint_name,
            checkpoint_order=checkpoint_count + 1
        )
        
        self.db.add(checkpoint)
        self.db.flush()
        
        return checkpoint

    def mark_checkpoint_reached(self, checkpoint_id: int):
        """标记检查点已到达"""
        checkpoint = self.db.query(TransactionCheckpoint)\
            .filter(TransactionCheckpoint.id == checkpoint_id)\
            .first()
        
        if checkpoint:
            checkpoint.is_reached = True
            checkpoint.reached_at = datetime.utcnow()
            self.db.flush()

    def _get_transaction(self, transaction_id: int) -> Optional[Transaction]:
        """获取事务"""
        return self.db.query(Transaction).filter(Transaction.id == transaction_id).first()

    def get_transaction_by_external_id(self, external_transaction_id: str) -> Optional[Transaction]:
        """通过外部事务ID获取事务"""
        return self.db.query(Transaction)\
            .filter(Transaction.transaction_id == external_transaction_id)\
            .first()

    def get_transaction_status(self, transaction_id: int) -> Optional[str]:
        """获取事务状态"""
        transaction = self._get_transaction(transaction_id)
        return transaction.status if transaction else None

    def get_transactions_by_context(self, context_type: str, context_id: int) -> List[Transaction]:
        """根据上下文获取事务"""
        return self.db.query(Transaction)\
            .filter(Transaction.context_type == context_type)\
            .filter(Transaction.context_id == context_id)\
            .order_by(Transaction.started_at.desc())\
            .all()

    def get_transaction_operations(self, transaction_id: int) -> List[TransactionOperation]:
        """获取事务的所有操作"""
        return self.db.query(TransactionOperation)\
            .filter(TransactionOperation.transaction_id == transaction_id)\
            .order_by(TransactionOperation.operation_order)\
            .all()

    def cleanup_stale_transactions(self, hours_threshold: int = 24):
        """清理长时间未完成的事务"""
        cutoff_time = datetime.utcnow() - datetime.timedelta(hours=hours_threshold)
        
        stale_transactions = self.db.query(Transaction)\
            .filter(Transaction.status == "pending")\
            .filter(Transaction.started_at < cutoff_time)\
            .all()
        
        for transaction in stale_transactions:
            self.rollback_transaction(transaction.id, "Transaction timeout")