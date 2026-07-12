"""解析上下文：在结构化导入链路中传递 db / ledger_id。"""

from __future__ import annotations

from contextvars import ContextVar, Token

from sqlalchemy.orm import Session

_parse_db: ContextVar[Session | None] = ContextVar("parse_db", default=None)
_parse_ledger_id: ContextVar[int | None] = ContextVar("parse_ledger_id", default=None)


def set_parse_context(
    *,
    db: Session | None = None,
    ledger_id: int | None = None,
) -> tuple[Token, Token]:
    db_token = _parse_db.set(db)
    ledger_token = _parse_ledger_id.set(ledger_id)
    return db_token, ledger_token


def reset_parse_context(db_token: Token, ledger_token: Token) -> None:
    _parse_db.reset(db_token)
    _parse_ledger_id.reset(ledger_token)


def get_parse_db() -> Session | None:
    return _parse_db.get()


def get_parse_ledger_id() -> int | None:
    return _parse_ledger_id.get()
