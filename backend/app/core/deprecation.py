"""Deprecated API 响应头中间件。

业务背景：api-boundary-governance-plan.md Phase 3 要求对已废弃的 API
（/api/unified-import、/api/parse）在响应头中标注，便于客户端程序化检测。

实现规范：
- `Deprecation: true` — IETF draft-ietf-httpapi-deprecation-header
- `Sunset: <HTTP-date>` — RFC 8594，告知计划移除时间

注意：
- 路径匹配须精确到前缀 + "/"，避免误匹配 /api/parser-engine 等
- 不修改请求/响应体，仅追加响应头
"""
from __future__ import annotations

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp

# 计划移除日期：从 2026-08-01 起 6 个月缓冲
# 格式遵循 RFC 7231 IMF-fixdate
SUNSET_DATE = "Mon, 01 Feb 2027 00:00:00 GMT"

# 已废弃 API 前缀（精确匹配或前缀 + "/"）
# 注意：不能用 startswith("/api/parse")，否则会误匹配 /api/parser-engine 等
DEPRECATED_PREFIXES: tuple[str, ...] = (
    "/api/unified-import",
    "/api/parse",
)


def _is_deprecated_path(path: str) -> bool:
    """判断请求路径是否命中已废弃前缀。

    匹配规则：path == prefix 或 path.startswith(prefix + "/")，
    避免 /api/parse 误匹配 /api/parser-engine。
    """
    for prefix in DEPRECATED_PREFIXES:
        if path == prefix or path.startswith(prefix + "/"):
            return True
    return False


class DeprecationHeaderMiddleware(BaseHTTPMiddleware):
    """给已废弃 API 的响应追加 Deprecation 与 Sunset 头。

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
        if _is_deprecated_path(request.url.path):
            response.headers["Deprecation"] = "true"
            response.headers["Sunset"] = self._sunset_date
            # Link 头指向替代主路径文档（RFC 8594 推荐）
            response.headers["Link"] = (
                '</api/import-jobs>; rel="successor-version"'
            )
        return response
