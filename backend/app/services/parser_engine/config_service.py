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

from app.core.config import get_settings
from app.db.session import get_db
from app.models.global_settings import GlobalSettings
from sqlalchemy.orm import Session


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
        db_config = db.query(GlobalSettings).filter(
            GlobalSettings.settings_key == "parser_engine"
        ).first()
    
    default_config = {
        "ai_provider": settings.ai_provider,
        "ai_base_url": settings.ai_base_url,
        "ai_model": settings.ai_model,
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
        return merged_config
    
    return default_config