"""往来单位内存缓存 — 供 routes_files / routes_counterparties 共享。"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models import Counterparty

_cache: dict[int, Counterparty] | None = None
_cache_ts: float = 0.0
_CACHE_TTL = 300.0


def get_counterparty_cache() -> dict[int, Counterparty] | None:
    return _cache


def get_cache_ts() -> float:
    return _cache_ts


def set_counterparty_cache(rows: list[Counterparty]) -> None:
    global _cache, _cache_ts
    _cache = {cp.id: cp for cp in rows}
    _cache_ts = time.monotonic()


def is_cache_expired() -> bool:
    global _cache, _cache_ts
    return _cache is None or (time.monotonic() - _cache_ts) > _CACHE_TTL


def invalidate() -> None:
    global _cache, _cache_ts
    _cache = None
    _cache_ts = 0.0


import logging

logger = logging.getLogger(__name__)
