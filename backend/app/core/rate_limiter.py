"""轻量级滑动窗口速率限制中间件。

业务背景：会计系统 API 必须有防滥用保护，满足《信息安全技术 网络安全等级保护基本要求》
中 "业务信息安全" 层面的访问控制要求。

实现方式：进程内滑动窗口（sliding window log），以客户端 IP + 路由为粒度。
- 无需外部依赖（无 Redis/数据库）
- 支持可配置的请求数 / 时间窗口
- 白名单路径（健康检查、文档）不受限制
- 超过阈值返回 429 Too Many Requests

注意：多实例部署时需替换为 Redis 共享存储。
当前版本适用于单机部署场景。
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp, Receive, Scope, Send

logger = logging.getLogger(__name__)

# 默认配置：每个 IP 每分钟最多 120 次请求
DEFAULT_WINDOW_SECONDS = 60
DEFAULT_MAX_REQUESTS = 120

# 白名单：这些路径不受速率限制
WHITELIST_PATHS = {
    "/health",
    "/api/ops/health",
    "/docs",
    "/redoc",
    "/openapi.json",
}


class SlidingWindowRateLimiter:
    """进程内滑动窗口限流器。

    以 (client_ip, route_path) 为 key，维护请求时间戳列表。
    每次请求清理窗口外的旧记录，检查当前窗口内请求数是否超限。
    """

    def __init__(
        self,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        max_requests: int = DEFAULT_MAX_REQUESTS,
    ) -> None:
        self.window_seconds = window_seconds
        self.max_requests = max_requests
        self._requests: dict[tuple[str, str], list[float]] = defaultdict(list)

    def is_allowed(self, client_ip: str, path: str) -> tuple[bool, int]:
        """检查请求是否允许通过。

        Returns:
            (allowed, retry_after_seconds)
        """
        key = (client_ip, path)
        now = time.time()
        window_start = now - self.window_seconds

        # 清理窗口外的旧记录
        timestamps = self._requests[key]
        cutoff = 0
        for i, ts in enumerate(timestamps):
            if ts >= window_start:
                cutoff = i
                break
        else:
            cutoff = len(timestamps)
        self._requests[key] = timestamps[cutoff:]

        # 检查是否超限
        if len(self._requests[key]) >= self.max_requests:
            oldest = self._requests[key][0]
            retry_after = int(self.window_seconds - (now - oldest)) + 1
            return False, max(retry_after, 1)

        # 记录本次请求
        self._requests[key].append(now)
        return True, 0

    def cleanup(self, max_age_seconds: int = 300) -> None:
        """清理过期的请求记录，防止内存泄漏。"""
        now = time.time()
        expired_keys: list[tuple[str, str]] = []
        for key, timestamps in self._requests.items():
            filtered = [ts for ts in timestamps if now - ts < max_age_seconds]
            if filtered:
                self._requests[key] = filtered
            else:
                expired_keys.append(key)
        for key in expired_keys:
            del self._requests[key]


# 全局单例限流器实例
_limiter = SlidingWindowRateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """FastAPI 速率限制中间件。

    使用方式：
        app.add_middleware(RateLimitMiddleware)

    配置：
        limiter = get_rate_limiter()
        limiter.max_requests = 200  # 动态调整
    """

    def __init__(
        self,
        app: ASGIApp,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        max_requests: int = DEFAULT_MAX_REQUESTS,
    ) -> None:
        super().__init__(app)
        self._limiter = SlidingWindowRateLimiter(
            window_seconds=window_seconds,
            max_requests=max_requests,
        )

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # 白名单路径直接放行
        if request.url.path in WHITELIST_PATHS:
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        allowed, retry_after = self._limiter.is_allowed(client_ip, path)
        if not allowed:
            logger.warning(
                "速率限制触发 ip=%s path=%s retry_after=%ds",
                client_ip, path, retry_after,
            )
            return Response(
                content='{"detail":"Too Many Requests","retry_after":' + str(retry_after) + "}",
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        return response


def get_rate_limiter() -> SlidingWindowRateLimiter:
    """获取全局限流器实例（用于动态配置）。"""
    return _limiter
