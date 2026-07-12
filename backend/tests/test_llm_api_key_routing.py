"""LLM 密钥掩码与 auto 路由配置。"""

from app.services.doc_parsing.parser_engine.config_service import (
    is_masked_api_key,
    resolve_api_key_for_use,
    resolve_effective_llm_config,
)


def test_is_masked_api_key():
    assert is_masked_api_key("********abcd") is True
    assert is_masked_api_key("sk-test-key") is False
    assert is_masked_api_key("") is False


def test_resolve_api_key_prefers_incoming():
    assert resolve_api_key_for_use("sk-new", "sk-old") == "sk-new"


def test_resolve_api_key_uses_stored_when_masked():
    assert resolve_api_key_for_use("********abcd", "sk-real-key") == "sk-real-key"


def test_resolve_effective_llm_config_auto_includes_cloud_fallback():
    from app.services.doc_parsing.parser_engine import config_service

    original = config_service.get_runtime_parser_engine_config

    def fake_runtime(_db=None):
        return {
            "ai_routing_mode": "auto",
            "ai_base_url": "http://local:11434/v1",
            "ai_model": "qwen2.5vl:latest",
            "ai_local_base_url": "http://edge.example:11434/v1",
            "ai_local_model": "qwen2.5vl:latest",
            "ai_cloud_base_url": "https://api.moonshot.cn/v1",
            "ai_cloud_model": "moonshot-v1-8k",
            "ai_cloud_api_key": "sk-cloud",
        }

    config_service.get_runtime_parser_engine_config = fake_runtime
    try:
        effective = resolve_effective_llm_config(None)
        assert effective["ai_base_url"] == "http://edge.example:11434/v1"
        assert effective["_cloud_fallback"]["ai_model"] == "moonshot-v1-8k"
    finally:
        config_service.get_runtime_parser_engine_config = original
