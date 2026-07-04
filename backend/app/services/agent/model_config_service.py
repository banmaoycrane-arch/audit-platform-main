# -*- coding: utf-8 -*-
"""
模块功能：模型配置状态服务
业务场景：向前端展示 AI 模型配置状态，便于判断当前 Agent 使用远程模型还是规则回退
政策依据：API Key 等敏感信息不得暴露到前端，模型调用状态需可审计、可解释
输入数据：后端环境变量中的模型供应商、模型名称、API Key 和回退策略配置
输出结果：不包含密钥原文的模型配置状态
创建日期：2026-06-19
更新记录：
    2026-06-19  初始创建模型配置状态服务
"""
from typing import Any

from app.core.config import get_settings


def get_model_config_status(settings: Any | None = None) -> dict[str, Any]:
    """
    功能描述：返回当前 AI 模型配置状态。
    业务逻辑：只返回供应商、模型名称、API Key 是否已配置、是否启用本地轻量识别和规则回退。
    会计口径：该状态用于解释 Agent 的能力来源，不代表任何财务处理结果。

    Args:
        settings: 配置对象，默认读取后端环境变量。

    Returns:
        dict: 不包含 API Key 原文的模型配置状态。

    注意事项：
        1. 返回值严禁包含 ai_api_key 或密钥片段。
        2. 模型不可用时，Agent 应回退到规则识别，避免业务入口完全不可用。
    """
    current_settings = settings or get_settings()
    remote_model_configured = bool(current_settings.ai_base_url and current_settings.ai_model)
    api_key_configured = bool(current_settings.ai_api_key)
    local_lightweight_model_enabled = bool(current_settings.ai_local_model_enabled)
    fallback_to_rules_enabled = bool(current_settings.ai_fallback_to_rules)

    if remote_model_configured:
        active_mode = "remote_model"
    elif local_lightweight_model_enabled:
        active_mode = "local_lightweight_rules"
    else:
        active_mode = "rules_only"

    return {
        "provider": current_settings.ai_provider,
        "model_name": current_settings.ai_model or None,
        "base_url_configured": bool(current_settings.ai_base_url),
        "api_key_configured": api_key_configured,
        "remote_model_configured": remote_model_configured,
        "local_lightweight_model_enabled": local_lightweight_model_enabled,
        "fallback_to_rules_enabled": fallback_to_rules_enabled,
        "fallback_strategy": "rules_intent_recognition" if fallback_to_rules_enabled else None,
        "active_mode": active_mode,
    }
