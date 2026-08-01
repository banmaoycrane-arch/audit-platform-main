from __future__ import annotations

import logging
from functools import wraps
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

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
            logger.warning("Bare exception caught in %s: %s", __name__, e, exc_info=True)
            logger.warning("事务执行失败，回滚后重新抛出: %s.%s error=%s", func.__module__, func.__name__, e)
            db.rollback()
            raise TransactionError(f"事务执行失败：{e}") from e

    return wrapper


def transaction_with_retry(
    max_attempts: int = 3,
    min_wait_seconds: float = 2.0,
    max_wait_seconds: float = 10.0,
    retryable_exceptions: tuple[type[Exception], ...] = (OperationalError, TimeoutError),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    带重试的事务装饰器。

    使用 tenacity 对 SQLAlchemy OperationalError / TimeoutError 进行指数退避重试。

    参数：
        max_attempts: 最大重试次数
        min_wait_seconds: 最小等待时间
        max_wait_seconds: 最大等待时间
        retryable_exceptions: 可重试的异常类型，默认 (OperationalError, TimeoutError)
    """

    @retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait_seconds, max=max_wait_seconds),
        reraise=True,
        retry=retry_if_exception_type(retryable_exceptions),
    )
    def _execute_with_retry(db: Session, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        try:
            return func(db, *args, **kwargs)
        except Exception as e:
            logger.warning("事务执行失败，回滚后重新抛出: %s.%s error=%s", func.__module__, func.__name__, e)
            db.rollback()
            raise TransactionError(f"事务执行失败：{e}") from e

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(db: Session, *args: Any, **kwargs: Any) -> T:
            return _execute_with_retry(db, func, *args, **kwargs)

        return wrapper

    return decorator


def retry_if_exception_type(exc_types: tuple[type[Exception], ...]):
    """辅助函数：判断异常类型是否在可重试列表中。"""

    def predicate(exc: BaseException) -> bool:
        return isinstance(exc, exc_types)

    return predicate
