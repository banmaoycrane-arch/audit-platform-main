"""Deprecated API 响应头中间件测试。

验证项：
- 命中已废弃前缀的响应含 Deprecation/Sunset/Link 头
- 非废弃路径（含易混淆的 /api/parser-engine）不含
- _is_deprecated_path 路径匹配边界正确

治理依据：api-boundary-governance-plan.md §五 Phase 3
"""
from fastapi.testclient import TestClient

from app.core.deprecation import _is_deprecated_path
from app.main import app


def test_is_deprecated_path_unit() -> None:
    """_is_deprecated_path 边界匹配：精确、子路径、不误匹配近似前缀。"""
    # 命中：精确匹配
    assert _is_deprecated_path("/api/unified-import") is True
    assert _is_deprecated_path("/api/parse") is True
    # 命中：子路径
    assert _is_deprecated_path("/api/unified-import/jobs") is True
    assert _is_deprecated_path("/api/unified-import/jobs/123/result") is True
    assert _is_deprecated_path("/api/parse/contract") is True
    assert _is_deprecated_path("/api/parse/invoice") is True

    # 反例：近似前缀不可误匹配（关键安全约束）
    assert _is_deprecated_path("/api/parser-engine") is False
    assert _is_deprecated_path("/api/parser-engine/status") is False
    assert _is_deprecated_path("/api/parser-engine/corrections") is False
    assert _is_deprecated_path("/api/parser-engine/evolution") is False
    assert _is_deprecated_path("/api/parser-voucher") is False

    # 反例：其他正常路径
    assert _is_deprecated_path("/health") is False
    assert _is_deprecated_path("/api/import-jobs") is False
    assert _is_deprecated_path("/api/vouchers") is False
    assert _is_deprecated_path("/") is False

    # 反例：前缀字符串相同但非完整段（防止 /api/parseXYZ 误匹配）
    assert _is_deprecated_path("/api/parseXYZ") is False
    assert _is_deprecated_path("/api/unified-import-v2") is False


def test_deprecation_headers_on_parse_endpoint() -> None:
    """命中 /api/parse/* 的响应（即使 4xx）也带 Deprecation/Sunset/Link。"""
    client = TestClient(app)
    # 缺 organization_id 会返回 422，但中间件在响应阶段加 header
    response = client.post("/api/parse/contract", json={})
    assert response.status_code == 422
    assert response.headers["Deprecation"] == "true"
    assert "Sunset" in response.headers
    assert response.headers["Link"] == '</api/import-jobs>; rel="successor-version"'


def test_deprecation_headers_on_unified_import_endpoint() -> None:
    """命中 /api/unified-import/* 的响应（即使 4xx）也带 Deprecation/Sunset/Link。"""
    client = TestClient(app)
    # 该路由有 get_current_user 依赖，无 token 返回 401，但中间件仍加 header
    response = client.post("/api/unified-import/jobs")
    assert response.status_code == 401
    assert response.headers["Deprecation"] == "true"
    assert "Sunset" in response.headers
    assert response.headers["Link"] == '</api/import-jobs>; rel="successor-version"'


def test_no_deprecation_headers_on_parser_engine() -> None:
    """非废弃路径 /api/parser-engine/status 不带 Deprecation 头（防误匹配回归）。"""
    client = TestClient(app)
    response = client.get("/api/parser-engine/status")
    assert response.status_code == 200
    assert "Deprecation" not in response.headers
    assert "Sunset" not in response.headers


def test_no_deprecation_headers_on_health() -> None:
    """健康检查路径不带 Deprecation 头。"""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert "Deprecation" not in response.headers
    assert "Sunset" not in response.headers
