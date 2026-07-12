# -*- coding: utf-8 -*-
"""
模块功能：解析引擎运行时配置服务
业务场景：从数据库读取解析引擎配置，提供统一的配置获取接口
政策依据：无
输入数据：数据库连接
输出结果：解析引擎配置字典
创建日期：2026-06-26
"""

from typing import Any, Dict

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.models.global_settings import GlobalSettings
from sqlalchemy.orm import Session


def resolve_parse_model(config: Dict[str, Any]) -> str:
    """非结构化文件解析 / 视觉多模态模型（ai_model）。"""
    return str(config.get("ai_model") or config.get("llm_preferred_model") or "").strip()


def resolve_reasoning_model(config: Dict[str, Any]) -> str:
    """合规审查、语义推理模型；未单独配置时回退到解析模型。"""
    reasoning = str(config.get("ai_reasoning_model") or "").strip()
    if reasoning:
        return reasoning
    return resolve_parse_model(config)


def resolve_primary_chat_model(config: Dict[str, Any]) -> str:
    """兼容旧调用：等同于 resolve_reasoning_model。"""
    return resolve_reasoning_model(config)


def config_for_reasoning_llm(config: Dict[str, Any]) -> Dict[str, Any]:
    """供 LlmClientService 使用的推理模型配置（覆盖 ai_model 字段）。"""
    merged = dict(config)
    merged["ai_model"] = resolve_reasoning_model(config)
    return merged


def config_for_parse_llm(config: Dict[str, Any]) -> Dict[str, Any]:
    """供解析引擎使用的配置（确保 ai_model 为解析模型）。"""
    merged = dict(config)
    merged["ai_model"] = resolve_parse_model(config)
    return merged


def resolve_effective_comparison_engines(config: Dict[str, Any]) -> list[str]:
    """多引擎对比使用的模型列表；以解析模型为主，不与推理模型混用。"""
    settings = get_settings()
    primary = resolve_parse_model(config)
    raw = str(config.get("llm_comparison_engines") or "")
    engines = [item.strip() for item in raw.split(",") if item.strip()]
    default_engines = [item.strip() for item in settings.llm_comparison_engines.split(",") if item.strip()]
    if not engines or engines == default_engines:
        return [primary] if primary else engines
    if primary and primary not in engines:
        return [primary, *engines]
    return engines


def model_supports_thinking_stream(model_name: str) -> bool:
    """
    Ollama 流式 API 的 message.thinking 仅部分推理模型支持。
    qwen2.5 / qwen2.5vl、gpt-oss 等通常只有 content，无思索通道。
    """
    lower = (model_name or "").lower()
    if not lower or "embed" in lower:
        return False
    thinking_markers = (
        "deepseek-r1",
        "qwq",
        "qwen3",
        ":thinking",
        "-think",
        "reasoner",
        "r1",
    )
    return any(marker in lower for marker in thinking_markers)


def normalize_parser_engine_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """保存/读取时同步解析模型与对比引擎；推理模型独立保留。"""
    result = dict(config)
    result["ai_reasoning_model"] = str(result.get("ai_reasoning_model") or "").strip()
    parse_model = resolve_parse_model(result)
    if parse_model:
        result["llm_preferred_model"] = parse_model
        engines = resolve_effective_comparison_engines(result)
        result["llm_comparison_engines"] = ",".join(engines)
    return result


def get_runtime_parser_engine_config(db: Session | None = None) -> Dict[str, Any]:
    """
    获取解析引擎的运行时配置
    
    功能描述：优先从数据库获取配置，如果数据库中没有则返回默认配置
    业务逻辑：
        1. 尝试从数据库读取 parser_engine 配置
        2. 如果数据库中没有配置，返回 .env 文件中的默认配置
        3. 将数据库配置与默认配置合并，确保所有字段都有值
    
    Args:
        db: 数据库会话，可选
    
    Returns:
        Dict: 包含所有解析引擎配置的字典
    """
    settings = get_settings()
    
    db_config = None
    if db:
        try:
            db_config = db.query(GlobalSettings).filter(
                GlobalSettings.settings_key == "parser_engine"
            ).first()
        except SQLAlchemyError:
            db_config = None
    
    default_config = {
        "ai_provider": settings.ai_provider,
        "ai_base_url": settings.ai_base_url,
        "ai_model": settings.ai_model,
        "ai_reasoning_model": getattr(settings, "ai_reasoning_model", "") or "",
        "ai_api_key": settings.ai_api_key or None,
        "ai_local_model_enabled": settings.ai_local_model_enabled,
        "ai_fallback_to_rules": settings.ai_fallback_to_rules,
        
        "llm_max_concurrent_models": settings.llm_max_concurrent_models,
        "llm_memory_limit_mb": settings.llm_memory_limit_mb,
        "llm_preferred_model": settings.llm_preferred_model,
        "llm_fallback_model": settings.llm_fallback_model,
        "llm_timeout_seconds": settings.llm_timeout_seconds,
        
        "llm_enable_parallel_parsing": settings.llm_enable_parallel_parsing,
        "llm_parallel_timeout_seconds": settings.llm_parallel_timeout_seconds,
        
        "llm_result_selection_mode": settings.llm_result_selection_mode,
        "llm_confidence_threshold_auto": settings.llm_confidence_threshold_auto,
        "llm_confidence_threshold_user": settings.llm_confidence_threshold_user,
        
        "llm_multi_engine_enabled": settings.llm_multi_engine_enabled,
        "llm_comparison_mode": settings.llm_comparison_mode,
        "llm_comparison_strategy": settings.llm_comparison_strategy,
        "llm_comparison_engines": settings.llm_comparison_engines,
        "llm_engine_weights": settings.llm_engine_weights,
        "llm_agreement_threshold": settings.llm_agreement_threshold,
        "llm_save_all_results": settings.llm_save_all_results,
        "llm_knowledge_base": settings.llm_knowledge_base or None,
    }
    
    if db_config and db_config.settings_value:
        merged_config = {**default_config, **db_config.settings_value}
        return normalize_parser_engine_config(merged_config)

    return normalize_parser_engine_config(default_config)
