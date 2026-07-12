"""Step4 staging 凭证预览读缓存：减轻重复 SQL 分组压力。"""

from __future__ import annotations

import time
from typing import Any

_CACHE_TTL_SECONDS = 45
_stats_cache: dict[int, tuple[float, dict[str, Any]]] = {}
_list_cache: dict[tuple[Any, ...], tuple[float, tuple[list[dict[str, Any]], int, dict[str, Any]]]] = {}


def invalidate_staging_preview_cache(job_id: int) -> None:
    _stats_cache.pop(job_id, None)
    stale_keys = [key for key in _list_cache if key[0] == job_id]
    for key in stale_keys:
        _list_cache.pop(key, None)


def get_cached_review_stats(job_id: int) -> dict[str, Any] | None:
    cached = _stats_cache.get(job_id)
    if not cached:
        return None
    expires_at, payload = cached
    if time.monotonic() > expires_at:
        _stats_cache.pop(job_id, None)
        return None
    return payload


def set_cached_review_stats(job_id: int, stats: dict[str, Any]) -> None:
    _stats_cache[job_id] = (time.monotonic() + _CACHE_TTL_SECONDS, stats)


def get_cached_voucher_page(
    job_id: int,
    *,
    review_filter: str,
    search: str | None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int, dict[str, Any]] | None:
    key = (job_id, review_filter, (search or "").strip().lower(), limit, offset)
    cached = _list_cache.get(key)
    if not cached:
        return None
    expires_at, payload = cached
    if time.monotonic() > expires_at:
        _list_cache.pop(key, None)
        return None
    return payload


def set_cached_voucher_page(
    job_id: int,
    *,
    review_filter: str,
    search: str | None,
    limit: int,
    offset: int,
    page_items: list[dict[str, Any]],
    total: int,
    review_stats: dict[str, Any],
) -> None:
    key = (job_id, review_filter, (search or "").strip().lower(), limit, offset)
    _list_cache[key] = (
        time.monotonic() + _CACHE_TTL_SECONDS,
        (page_items, total, review_stats),
    )
