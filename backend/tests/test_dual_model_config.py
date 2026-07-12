"""双模型配置：解析模型与推理模型分离。"""

from app.services.doc_parsing.parser_engine.config_service import (
    config_for_parse_llm,
    config_for_reasoning_llm,
    normalize_parser_engine_config,
    resolve_parse_model,
    resolve_reasoning_model,
)


def test_resolve_dual_models():
    config = {
        "ai_model": "qwen2.5vl:latest",
        "ai_reasoning_model": "deepseek-r1:8b",
        "llm_comparison_engines": "qwen2.5-14b,qwen2.5-7b",
    }
    normalized = normalize_parser_engine_config(config)

    assert resolve_parse_model(normalized) == "qwen2.5vl:latest"
    assert resolve_reasoning_model(normalized) == "deepseek-r1:8b"
    assert normalized["llm_preferred_model"] == "qwen2.5vl:latest"
    assert normalized["llm_comparison_engines"].startswith("qwen2.5vl:latest")

    parse_cfg = config_for_parse_llm(normalized)
    reasoning_cfg = config_for_reasoning_llm(normalized)
    assert parse_cfg["ai_model"] == "qwen2.5vl:latest"
    assert reasoning_cfg["ai_model"] == "deepseek-r1:8b"


def test_reasoning_none_in_db_falls_back_to_parse():
    config = normalize_parser_engine_config(
        {"ai_model": "qwen2.5vl:latest", "ai_reasoning_model": None}
    )
    assert config["ai_reasoning_model"] == ""
    assert resolve_reasoning_model(config) == "qwen2.5vl:latest"
    assert config_for_reasoning_llm(config)["ai_model"] == "qwen2.5vl:latest"
    assert config_for_parse_llm(config)["ai_model"] == "qwen2.5vl:latest"


def test_dual_models_do_not_swap():
    config = normalize_parser_engine_config(
        {
            "ai_model": "qwen2.5vl:latest",
            "ai_reasoning_model": "deepseek-r1:8b",
        }
    )
    assert config_for_parse_llm(config)["ai_model"] == "qwen2.5vl:latest"
    assert config_for_reasoning_llm(config)["ai_model"] == "deepseek-r1:8b"


def test_reasoning_falls_back_to_parse_model():
    config = normalize_parser_engine_config({"ai_model": "qwen2.5:7b"})
    assert resolve_reasoning_model(config) == "qwen2.5:7b"
    assert config_for_reasoning_llm(config)["ai_model"] == "qwen2.5:7b"
