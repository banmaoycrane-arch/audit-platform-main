"""Agent 大模型配置解析：优先 DB 解析引擎配置，回退 .env。"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.agent.llm_client_service import LightweightLLMClient
from app.services.doc_parsing.parser_engine.config_service import (
    get_runtime_parser_engine_config,
    resolve_effective_llm_config,
)


def resolve_agent_llm_config(db: Session | None = None) -> dict[str, Any]:
    runtime = resolve_effective_llm_config(db)
    settings = get_settings()
    source = "env"
    if db:
        from app.models.global_settings import GlobalSettings

        row = db.query(GlobalSettings).filter(GlobalSettings.settings_key == "parser_engine").first()
        if row and row.settings_value:
            source = "parser_engine_db"
    return {
        "source": source,
        "ai_provider": runtime.get("ai_provider") or settings.ai_provider,
        "ai_base_url": runtime.get("ai_base_url") or settings.ai_base_url,
        "ai_model": runtime.get("ai_model") or settings.ai_model,
        "ai_api_key": runtime.get("ai_api_key") or settings.ai_api_key,
        "llm_timeout_seconds": int(runtime.get("llm_timeout_seconds") or settings.llm_timeout_seconds or 30),
        "is_ollama": _is_ollama_url(str(runtime.get("ai_base_url") or settings.ai_base_url or "")),
    }


def _is_ollama_url(base_url: str) -> bool:
    lowered = base_url.lower()
    return ":11434" in base_url or "ollama" in lowered


def build_agent_llm_client(db: Session | None = None) -> LightweightLLMClient:
    config = resolve_agent_llm_config(db)
    return LightweightLLMClient(
        config={
            "ai_base_url": config.get("ai_base_url"),
            "ai_model": config.get("ai_model"),
            "ai_api_key": config.get("ai_api_key"),
            "llm_timeout_seconds": config.get("llm_timeout_seconds"),
        }
    )
