"""Deprecated API 响应头中间件。

业务背景：
- Phase 3: 废弃 IMP-B (/api/unified-import)、IMP-C (/api/parse)
- Phase 2: 废弃 ENTRIES-V1 (/api/entries/vouchers/*)，指向 /api/vouchers 主路径
- Phase 4: TAG-A (/api/entries/{id}/tags GET/POST/DELETE) 走 307 重定向，header 由替代路径返回

实现规范：
- `Deprecation: true` — IETF draft-ietf-httpapi-deprecation-header
- `Sunset: <HTTP-date>` — RFC 8594，计划移除时间
- `Link: </api/...>; rel="successor-version"` — RFC 8594 指向替代主路径

注意：
- 路径匹配须精确，避免 /api/parse 误匹配 /api/parser-engine
"""
from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

# 计划移除日期：从 2026-08-01 起 6 个月缓冲；格式 RFC 7231 IMF-fixdate
SUNSET_DATE = "Mon, 01 Feb 2027 00:00:00 GMT"

# (废弃前缀, 替代主路径) 列表。匹配规则：path == prefix 或 path.startswith(prefix + "/")。
# 不能用 startswith("/api/parse")，避免误匹配 /api/parser-engine。
DEPRECATED_PREFIX_RULES: tuple[tuple[str, str], ...] = (
    ("/api/unified-import", "/api/import-jobs"),
    ("/api/parse", "/api/import-jobs"),
    ("/api/entries/vouchers", "/api/vouchers"),
)


def _match_successor(path: str) -> str | None:
    """返回命中的替代主路径；未命中返回 None。

    匹配规则：path == prefix 或 path.startswith(prefix + "/")。
    """
    for prefix, successor in DEPRECATED_PREFIX_RULES:
        if path == prefix or path.startswith(prefix + "/"):
            return successor
    return None


class DeprecationHeaderMiddleware(BaseHTTPMiddleware):
    """给已废弃 API 的响应追加 Deprecation、Sunset 与 Link 头。

    使用方式：
        app.add_middleware(DeprecationHeaderMiddleware)
    """

    def __init__(self, app: ASGIApp, sunset_date: str = SUNSET_DATE) -> None:
        super().__init__(app)
        self._sunset_date = sunset_date

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)
        successor = _match_successor(request.url.path)
        if successor is not None:
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = self._sunset_date
            # RFC 8594 Link 头指向替代主路径
            response.headers["Link"] = f'<{successor}>; rel="successor-version"'
        return response
