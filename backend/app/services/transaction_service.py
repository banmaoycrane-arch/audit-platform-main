from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from sqlalchemy.exc import OperationalError, TimeoutError
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_exponential

T = TypeVar("T")


class TransactionError(Exception):
    """事务执行异常。"""
    pass


def transaction(
    func: Callable[..., T],
) -> Callable[..., T]:
    """
    事务装饰器。

    自动管理 SQLAlchemy Session 事务：
    1. 执行被装饰函数
    2. 成功时提交事务
    3. 失败时回滚事务并重新抛出异常

    使用方式：
        @transaction
        def create_voucher(db: Session, ...) -> Voucher:
            ...

    注意：
        - 被装饰函数的第一个参数必须是 Session 对象（命名为 db）
        - 函数内部不应手动调用 db.commit() 或 db.rollback()
        - 如果需要在函数内部控制事务边界，使用 db.begin_nested() 创建嵌套事务
    """

    @wraps(func)
    def wrapper(db: Session, *args: Any, **kwargs: Any) -> T:
        try:
            result = func(db, *args, **kwargs)
            db.commit()
            return result
        except Exception as e:
            db.rollback()
            raise TransactionError(f"事务执行失败：{e}") from e

    return wrapper


def transaction_with_retry(
    max_attempts: int = 3,
    min_wait_seconds: float = 2.0,
    max_wait_seconds: float = 10.0,
    auto_commit: bool = True,
):
    """
    带重试机制的事务装饰器。

    对数据库瞬时错误（连接超时、锁等待超时等）进行指数退避重试。

    参数：
        max_attempts: 最大重试次数，默认 3
        min_wait_seconds: 最小等待时间，默认 2 秒
        max_wait_seconds: 最大等待时间，默认 10 秒
        auto_commit: 是否自动提交事务，默认 True。
                     当设置为 False 时，函数内部不做 commit/rollback，
                     由调用方管理事务边界。

    使用方式：
        @transaction_with_retry(max_attempts=3)
        def create_voucher(db: Session, ...) -> Voucher:
            ...

        @transaction_with_retry(max_attempts=3, auto_commit=False)
        def create_voucher_nested(db: Session, ...) -> Voucher:
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(db: Session, *args: Any, **kwargs: Any) -> T:
            @retry(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(
                    multiplier=1, min=min_wait_seconds, max=max_wait_seconds
                ),
                retry=(
                    lambda retry_state: isinstance(
                        retry_state.outcome.exception(),
                        (OperationalError, TimeoutError),
                    )
                ),
            )
            def execute_with_retry() -> T:
                try:
                    result = func(db, *args, **kwargs)
                    if auto_commit:
                        db.commit()
                    return result
                except (OperationalError, TimeoutError):
                    if auto_commit:
                        db.rollback()
                    raise
                except Exception as e:
                    if auto_commit:
                        db.rollback()
                        raise TransactionError(f"事务执行失败：{e}") from e
                    raise

            return execute_with_retry()

        return wrapper

    return decorator


def nested_transaction(db: Session):
    """
    创建嵌套事务（Savepoint）。

    在已有的事务内创建保存点，可以独立回滚到保存点而不影响外层事务。

    使用方式：
        with nested_transaction(db) as savepoint:
            try:
                # 执行操作
                ...
                savepoint.commit()
            except Exception:
                savepoint.rollback()
                raise
    """
    return db.begin_nested()


def ensure_transaction_boundary(db: Session):
    """
    确保当前操作在事务边界内。

    如果当前 Session 没有活跃事务，创建一个新事务。
    返回一个上下文管理器，退出时根据异常状态提交或回滚。

    使用方式：
        with ensure_transaction_boundary(db):
            # 执行需要事务保护的操作
            ...
    """
    return db.begin()
