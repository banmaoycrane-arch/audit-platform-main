"""Deprecated API 响应头中间件测试。

验证项：
- 命中已废弃前缀的响应含 Deprecation/Sunset/Link 头，且 Link 指向正确的替代主路径
- 非废弃路径（含易混淆的 /api/parser-engine、/api/entries/{id} 等）不含
- _match_successor 路径匹配边界正确

治理依据：api-boundary-governance-plan.md §五 Phase 2 + Phase 3
"""
from fastapi.testclient import TestClient

from app.core.deprecation import _match_successor
from app.main import app


def test_match_successor_unit() -> None:
    """_match_successor 边界匹配：精确、子路径、不误匹配近似前缀；返回正确 successor。"""
    # 命中 IMP-B → /api/import-jobs
    assert _match_successor("/api/unified-import") == "/api/import-jobs"
    assert _match_successor("/api/unified-import/jobs") == "/api/import-jobs"
    assert _match_successor("/api/unified-import/jobs/123/result") == "/api/import-jobs"

    # 命中 IMP-C → /api/import-jobs
    assert _match_successor("/api/parse") == "/api/import-jobs"
    assert _match_successor("/api/parse/contract") == "/api/import-jobs"
    assert _match_successor("/api/parse/invoice") == "/api/import-jobs"

    # 命中 ENTRIES-V1 → /api/vouchers
    assert _match_successor("/api/entries/vouchers") == "/api/vouchers"
    assert _match_successor("/api/entries/vouchers/lines") == "/api/vouchers"
    assert _match_successor("/api/entries/vouchers/batch-delete") == "/api/vouchers"
    assert _match_successor("/api/entries/vouchers/123/review") == "/api/vouchers"
    assert _match_successor("/api/entries/vouchers/review-batch") == "/api/vouchers"
    assert _match_successor("/api/entries/vouchers/123/unreview") == "/api/vouchers"

    # 反例：近似前缀不可误匹配（关键安全约束）
    assert _match_successor("/api/parser-engine") is None
    assert _match_successor("/api/parser-engine/status") is None
    assert _match_successor("/api/parser-engine/corrections") is None
    assert _match_successor("/api/parser-voucher") is None

    # 反例：纯 entries 子路径（非 vouchers）不应命中
    assert _match_successor("/api/entries") is None
    assert _match_successor("/api/entries/123") is None
    assert _match_successor("/api/entries/123/tags") is None  # TAG-A 走 307 redirect，header 由替代路径响应
    assert _match_successor("/api/entries/batch-review") is None
    assert _match_successor("/api/entries/chronological") is None
    assert _match_successor("/api/entries/review-stats") is None

    # 反例：其他正常路径
    assert _match_successor("/health") is None
    assert _match_successor("/api/import-jobs") is None
    assert _match_successor("/api/vouchers") is None
    assert _match_successor("/") is None

    # 反例：前缀字符串相同但非完整段（防止 /api/parseXYZ 误匹配）
    assert _match_successor("/api/parseXYZ") is None
    assert _match_successor("/api/unified-import-v2") is None
    # entries/vouchersX 也不应命中（防止段边界误匹配）
    assert _match_successor("/api/entries/vouchersXYZ") is None


def test_deprecation_headers_on_parse_endpoint() -> None:
    """命中 /api/parse/* 的响应（即使 4xx）也带 Deprecation/Sunset/Link，Link 指向 /api/import-jobs。"""
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


def test_deprecation_headers_on_entries_vouchers_endpoint() -> None:
    """ENTRIES-V1: /api/entries/vouchers 响应带 Deprecation/Sunset/Link，Link 指向 /api/vouchers。"""
    client = TestClient(app)
    # 有 get_current_user 依赖：无鉴权返回 401；中间件在响应后仍加 header
    response = client.get("/api/entries/vouchers")
    assert response.status_code in (401, 422)
    assert response.headers["Deprecation"] == "true"
    assert "Sunset" in response.headers
    assert response.headers["Link"] == '</api/vouchers>; rel="successor-version"'


def test_deprecation_headers_on_entries_vouchers_lines() -> None:
    """ENTRIES-V1: /api/entries/vouchers/lines 也命中废弃前缀。"""
    client = TestClient(app)
    response = client.get("/api/entries/vouchers/lines")
    assert response.status_code in (401, 422)
    assert response.headers["Deprecation"] == "true"
    assert response.headers["Link"] == '</api/vouchers>; rel="successor-version"'


def test_deprecation_headers_on_entries_vouchers_batch_delete() -> None:
    """ENTRIES-V1: /api/entries/vouchers/batch-delete POST 也命中废弃前缀。"""
    client = TestClient(app)
    response = client.post("/api/entries/vouchers/batch-delete", json={})
    # 401 无鉴权；仍应加 Deprecation header
    assert response.status_code in (401, 422)
    assert response.headers["Deprecation"] == "true"
    assert response.headers["Link"] == '</api/vouchers>; rel="successor-version"'


def test_no_deprecation_headers_on_parser_engine() -> None:
    """非废弃路径 /api/parser-engine/status 不带 Deprecation 头（防误匹配回归）。"""
    client = TestClient(app)
    response = client.get("/api/parser-engine/status")
    assert response.status_code == 200
    assert "Deprecation" not in response.headers
    assert "Sunset" not in response.headers


def test_no_deprecation_headers_on_entries_detail() -> None:
    """纯 entries 子路径（GET /api/entries/{id}）不带 Deprecation 头（非 ENTRIES-V1 段）。"""
    client = TestClient(app)
    # 缺鉴权 → 401；但不应有 Deprecation header
    response = client.get("/api/entries/123")
    assert response.status_code == 401
    assert "Deprecation" not in response.headers


def test_no_deprecation_headers_on_vouchers_main() -> None:
    """主路径 /api/vouchers 本身当然不带 Deprecation 头。"""
    client = TestClient(app)
    response = client.get("/api/vouchers")
    assert response.status_code in (401, 422)
    assert "Deprecation" not in response.headers


def test_no_deprecation_headers_on_health() -> None:
    """健康检查路径不带 Deprecation 头。"""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert "Deprecation" not in response.headers
    assert "Sunset" not in response.headers
