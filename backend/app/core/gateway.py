# -*- coding: utf-8 -*-
"""
模块功能：后端内部网关层
业务场景：所有 API 请求进入业务路由前后的统一治理
政策依据：财务系统内部控制要求，关键请求需可追踪、错误需可解释、敏感信息需隐藏
输入数据：HTTP 请求路径、请求头、异常信息
输出结果：统一请求编号、安全响应头、统一错误响应
创建日期：2026-06-19
更新记录：
    2026-06-19  增加 request_id、安全响应头和统一错误响应处理
"""

from typing import Any, Awaitable, Callable
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response


class GatewayMiddleware(BaseHTTPMiddleware):
    """
    功能描述：为所有后端请求补充统一网关信息。
    业务逻辑：为每次请求生成 request_id，并在响应头中返回，方便排查导入、结账、审计等问题。
    会计口径：不改变任何记账、审计和报表业务数据，只做请求治理。

    Args:
        app: FastAPI 应用实例。

    Returns:
        Response: 带 request_id 和安全响应头的 HTTP 响应。

    注意事项：
        1. 第一阶段不强制所有接口鉴权，避免影响现有业务流程。
    """

    async def dispatch(self, request: Request, call_next: Callable[[StarletteRequest], Awaitable[Response]]) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response


def build_error_response(
    request: Request,
    status_code: int,
    message: str,
    error_code: str,
    details: Any | None = None,
    legacy_detail: Any | None = None,
) -> JSONResponse:
    """
    功能描述：构造统一错误响应。
    业务逻辑：把技术异常转换为前端稳定可展示的业务错误格式。
    会计口径：错误响应保留 request_id，便于追踪财务数据操作问题。

    Args:
        request: 当前 HTTP 请求。
        status_code: HTTP 状态码。
        message: 用户可理解的错误说明。
        error_code: 稳定错误编码。
        details: 错误明细，通常用于参数校验。
        legacy_detail: 兼容 FastAPI 原有 detail 字段，避免影响既有前端和测试。

    Returns:
        JSONResponse: 统一格式错误响应。

    注意事项：
        1. 未预期异常不返回内部堆栈，避免暴露敏感信息。
    """
    request_id = getattr(request.state, "request_id", str(uuid4()))
    payload = {
        "detail": message if legacy_detail is None else legacy_detail,
        "error": {
            "code": error_code,
            "message": message,
            "details": details,
            "request_id": request_id,
        }
    }
    return JSONResponse(
        status_code=status_code,
        content=payload,
        headers={"X-Request-ID": request_id},
    )


def configure_gateway(app: FastAPI) -> None:
    """
    功能描述：注册后端内部网关能力。
    业务逻辑：集中注册请求追踪、安全响应头和统一错误处理。
    会计口径：网关层只处理通用治理，不写入或修改凭证、科目、期间等业务数据。

    Args:
        app: FastAPI 应用实例。

    Returns:
        None: 直接修改 FastAPI 应用配置。

    注意事项：
        1. 该函数应在应用创建后、路由挂载前调用。
    """
    app.add_middleware(GatewayMiddleware)

    @app.exception_handler(HTTPException)
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException | StarletteHTTPException) -> JSONResponse:
        detail = exc.detail
        message = "请求处理失败"
        details = None
        
        if hasattr(detail, "get"):
            message = str(detail.get("message", "请求处理失败"))
            details = detail
        elif isinstance(detail, str):
            message = detail
        
        return build_error_response(
            request=request,
            status_code=exc.status_code,
            message=message,
            error_code="http_error",
            details=details,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        validation_details = exc.errors()
        return build_error_response(
            request=request,
            status_code=422,
            message="请求参数不符合系统要求，请检查输入内容",
            error_code="validation_error",
            details=validation_details,
            legacy_detail=validation_details,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return build_error_response(
            request=request,
            status_code=500,
            message="系统处理异常，请联系管理员并提供请求编号",
            error_code="internal_server_error",
            details=None,
        )
