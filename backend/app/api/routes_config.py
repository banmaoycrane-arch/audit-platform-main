from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.global_settings import GlobalSettings
from app.models.user import User
from app.services.parser_engine.config_service import get_runtime_parser_engine_config
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/config", tags=["config"])


def _mask_api_key(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) <= 4:
        return "****"
    return f"{'*' * (len(value) - 4)}{value[-4:]}"


def _mask_parser_engine_config(config: dict[str, Any]) -> dict[str, Any]:
    masked = dict(config)
    if masked.get("ai_api_key"):
        masked["ai_api_key"] = _mask_api_key(str(masked["ai_api_key"]))
    return masked


class ParserEngineConfig(BaseModel):
    ai_provider: str
    ai_base_url: str
    ai_model: str
    ai_api_key: str | None = None
    ai_local_model_enabled: bool
    ai_fallback_to_rules: bool
    
    llm_max_concurrent_models: int
    llm_memory_limit_mb: int
    llm_preferred_model: str
    llm_fallback_model: str
    llm_timeout_seconds: int
    
    llm_enable_parallel_parsing: bool
    llm_parallel_timeout_seconds: int
    
    llm_result_selection_mode: str
    llm_confidence_threshold_auto: float
    llm_confidence_threshold_user: float
    
    llm_multi_engine_enabled: bool
    llm_comparison_mode: str
    llm_comparison_strategy: str
    llm_comparison_engines: str
    llm_engine_weights: str
    llm_agreement_threshold: float
    llm_save_all_results: bool
    llm_knowledge_base: str | None = None


class TestConnectionRequest(BaseModel):
    ai_base_url: str
    ai_model: str
    ai_api_key: str | None = None


@router.get("/parser-engine", response_model=ParserEngineConfig)
def get_parser_engine_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前解析引擎配置"""
    settings = get_settings()
    
    db_config = db.query(GlobalSettings).filter(
        GlobalSettings.settings_key == "parser_engine"
    ).first()
    
    if db_config and db_config.settings_value:
        return _mask_parser_engine_config(db_config.settings_value)
    
    return _mask_parser_engine_config({
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
    })


@router.post("/parser-engine/test-connection")
def test_ai_connection(
    request: TestConnectionRequest,
    current_user: User = Depends(get_current_user),
):
    """
    测试AI模型连接是否可用。

    连接测试只做轻量级探活和模型存在性检查，避免触发 Ollama 加载大模型导致长时间无响应。
    """
    import json
    import time
    from urllib import request as url_request
    from urllib.error import HTTPError, URLError

    normalized_input_url = request.ai_base_url.rstrip("/")
    ollama_root_url = normalized_input_url[:-3] if normalized_input_url.endswith("/v1") else normalized_input_url
    is_ollama = ":11434" in normalized_input_url or "ollama" in normalized_input_url.lower()

    headers = {"Content-Type": "application/json"}
    if request.ai_api_key:
        headers["Authorization"] = f"Bearer {request.ai_api_key}"

    def fetch_json(url: str, timeout: int = 5) -> dict[str, Any]:
        req = url_request.Request(url, headers=headers, method="GET")
        with url_request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))

    def normalize_model_name(name: str) -> str:
        return name.removesuffix(":latest")

    def model_exists(models: list[str]) -> bool:
        expected = normalize_model_name(request.ai_model)
        return any(model == request.ai_model or normalize_model_name(model) == expected for model in models)

    start_time = time.time()
    errors: list[str] = []

    try:
        if is_ollama:
            try:
                tags_url = f"{ollama_root_url}/api/tags"
                data = fetch_json(tags_url, timeout=5)
                models = [model.get("name", "") for model in data.get("models", []) if model.get("name")]
                elapsed_ms = round((time.time() - start_time) * 1000)
                if model_exists(models):
                    return {
                        "success": True,
                        "message": "连接成功！Ollama 服务可达，模型已存在。",
                        "model": request.ai_model,
                        "base_url": request.ai_base_url,
                        "api_type": "ollama-tags",
                        "response_content": "模型列表探活成功",
                        "response_time_ms": elapsed_ms,
                    }
                return {
                    "success": False,
                    "message": f"Ollama 服务可达，但未找到模型 {request.ai_model}。请先获取模型列表并选择已安装模型。",
                    "model": request.ai_model,
                    "base_url": request.ai_base_url,
                    "api_type": "ollama-tags",
                    "available_models": models,
                    "response_time_ms": elapsed_ms,
                }
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                errors.append(f"Ollama /api/tags 探活失败: {exc}")

        models_url = f"{normalized_input_url}/models" if normalized_input_url.endswith("/v1") else f"{normalized_input_url}/v1/models"
        data = fetch_json(models_url, timeout=5)
        models = [item.get("id", "") for item in data.get("data", []) if item.get("id")]
        elapsed_ms = round((time.time() - start_time) * 1000)
        if not models or model_exists(models):
            return {
                "success": True,
                "message": "连接成功！模型服务可达。",
                "model": request.ai_model,
                "base_url": request.ai_base_url,
                "api_type": "openai-compatible-models",
                "response_content": "模型列表探活成功",
                "response_time_ms": elapsed_ms,
            }
        return {
            "success": False,
            "message": f"模型服务可达，但未找到模型 {request.ai_model}。请检查模型名称。",
            "model": request.ai_model,
            "base_url": request.ai_base_url,
            "api_type": "openai-compatible-models",
            "available_models": models,
            "response_time_ms": elapsed_ms,
        }
    except Exception as exc:
        errors.append(f"OpenAI兼容 /models 探活失败: {exc}")
        return {
            "success": False,
            "message": "连接失败: " + "; ".join(errors),
            "model": request.ai_model,
            "base_url": request.ai_base_url,
        }


@router.get("/provider-options")
def get_provider_options():
    """获取可用的AI供应商选项"""
    return {
        "providers": [
            {
                "value": "openai-compatible",
                "label": "OpenAI兼容（Ollama/vLLM等）",
                "description": "兼容OpenAI API的本地或局域网服务",
                "default_base_url": "http://localhost:11434/v1",
                "default_model": "qwen2.5:14b-chat",
                "requires_api_key": False,
                "has_model_list": True,
            },
            {
                "value": "deepseek",
                "label": "DeepSeek API",
                "description": "深度求索提供的云端API",
                "default_base_url": "https://api.deepseek.com/v1",
                "default_model": "deepseek-chat",
                "requires_api_key": True,
                "has_model_list": False,
            },
            {
                "value": "kimi",
                "label": "Kimi (月之暗面)",
                "description": "月之暗面提供的云端API",
                "default_base_url": "https://api.moonshot.cn/v1",
                "default_model": "moonshot-v1-8k",
                "requires_api_key": True,
                "has_model_list": False,
            },
            {
                "value": "zhipu",
                "label": "智谱AI (GLM)",
                "description": "智谱AI提供的云端API",
                "default_base_url": "https://open.bigmodel.cn/api/paas/v4",
                "default_model": "glm-4-flash",
                "requires_api_key": True,
                "has_model_list": False,
            },
            {
                "value": "qwen",
                "label": "通义千问 (阿里云)",
                "description": "阿里云通义千问API",
                "default_base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "default_model": "qwen-turbo",
                "requires_api_key": True,
                "has_model_list": False,
            },
        ],
        "models": [
            {"value": "qwen2.5:14b-chat", "label": "Qwen2.5-14B-Chat", "description": "高性能，适合精度要求高的场景"},
            {"value": "qwen2.5:7b-chat", "label": "Qwen2.5-7B-Chat", "description": "平衡性能和速度"},
            {"value": "qwen2.5:3b-chat", "label": "Qwen2.5-3B-Chat", "description": "快速，适合简单任务"},
            {"value": "deepseek-v2-chat", "label": "DeepSeek-V2-Chat", "description": "专业中文理解"},
            {"value": "yi:34b-chat", "label": "Yi-34B-Chat", "description": "超大模型，精度最高"},
            {"value": "deepseek-chat", "label": "DeepSeek-Chat", "description": "云端API专用"},
            {"value": "moonshot-v1-8k", "label": "Kimi-8K", "description": "Kimi云端API专用"},
            {"value": "moonshot-v1-32k", "label": "Kimi-32K", "description": "Kimi云端API专用（长上下文）"},
            {"value": "glm-4-flash", "label": "GLM-4-Flash", "description": "智谱AI云端API专用"},
            {"value": "glm-4-plus", "label": "GLM-4-Plus", "description": "智谱AI云端API专用"},
            {"value": "qwen-turbo", "label": "Qwen-Turbo", "description": "通义千问云端API专用"},
            {"value": "qwen-plus", "label": "Qwen-Plus", "description": "通义千问云端API专用"},
        ],
        "comparison_modes": [
            {"value": "parallel_all", "label": "并行调用所有引擎"},
            {"value": "sequential_fallback", "label": "顺序调用，失败降级"},
            {"value": "best_two", "label": "只调用前两个最佳引擎"},
        ],
        "comparison_strategies": [
            {"value": "weighted_vote", "label": "加权投票"},
            {"value": "highest_confidence", "label": "最高置信度"},
            {"value": "intersection", "label": "字段一致"},
            {"value": "union_llm_best", "label": "优先LLM"},
        ],
        "selection_modes": [
            {"value": "auto_best", "label": "自动选择最佳"},
            {"value": "user_choose", "label": "用户选择"},
            {"value": "hybrid", "label": "混合模式"},
        ],
    }


@router.get("/ollama-models")
def get_ollama_models(base_url: str = "http://localhost:11434"):
    """获取Ollama服务上的可用模型列表"""
    import json
    from urllib import request as url_request
    
    try:
        url = f"{base_url.rstrip('/').rstrip('/v1')}/api/tags"
        req = url_request.Request(url, method="GET")
        with url_request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
        
        models = []
        for model in data.get("models", []):
            name = model.get("name", "")
            size = model.get("size", 0)
            size_gb = round(size / (1024 * 1024 * 1024), 1)
            models.append({
                "value": name,
                "label": name,
                "description": f"大小: {size_gb} GB",
            })
        
        return {
            "success": True,
            "models": models,
            "count": len(models),
        }
        
    except Exception as e:
        return {
            "success": False,
            "message": f"获取模型列表失败: {str(e)}",
            "models": [],
        }


class LLMEngineCreateRequest(BaseModel):
    name: str
    provider: str
    base_url: str
    model: str
    api_key: str | None = None
    weight: float = 0.3
    enabled: bool = True


class LLMEngineUpdateRequest(BaseModel):
    name: str | None = None
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    weight: float | None = None
    enabled: bool | None = None


class LLMComparisonConfigRequest(BaseModel):
    comparison_strategy: str = "field_consensus"
    min_consensus_ratio: float = 0.5


@router.get("/parser-engine/llm-engines")
def get_llm_engines(db: Session = Depends(get_db)):
    """获取多LLM引擎配置列表"""
    from app.services.llm_engine_config_service import get_llm_engines_config
    config = get_llm_engines_config(db)
    return {
        "success": True,
        "engines": [e.to_dict() for e in config.engines],
        "comparison_strategy": config.comparison_strategy,
        "min_consensus_ratio": config.min_consensus_ratio,
    }


@router.post("/parser-engine/llm-engines")
def add_llm_engine(engine: LLMEngineCreateRequest, db: Session = Depends(get_db)):
    """添加一个LLM引擎"""
    from app.services.llm_engine_config_service import (
        add_llm_engine,
        LLMEngineConfig,
    )
    new_engine = LLMEngineConfig(
        id="",
        name=engine.name,
        provider=engine.provider,
        base_url=engine.base_url,
        model=engine.model,
        api_key=engine.api_key or "",
        weight=engine.weight,
        enabled=engine.enabled,
    )
    config = add_llm_engine(db, new_engine)
    return {
        "success": True,
        "message": "引擎添加成功",
        "engines": [e.to_dict() for e in config.engines],
    }


@router.put("/parser-engine/llm-engines/{engine_id}")
def update_llm_engine(engine_id: str, engine: LLMEngineUpdateRequest, db: Session = Depends(get_db)):
    """更新一个LLM引擎"""
    from app.services.llm_engine_config_service import update_llm_engine
    result = update_llm_engine(db, engine_id, engine.model_dump(exclude_unset=True))
    if result is None:
        raise HTTPException(status_code=404, detail="引擎不存在")
    return {
        "success": True,
        "message": "引擎更新成功",
        "engines": [e.to_dict() for e in result.engines],
    }


@router.delete("/parser-engine/llm-engines/{engine_id}")
def delete_llm_engine(engine_id: str, db: Session = Depends(get_db)):
    """删除一个LLM引擎"""
    from app.services.llm_engine_config_service import delete_llm_engine
    result = delete_llm_engine(db, engine_id)
    if result is None:
        raise HTTPException(status_code=404, detail="引擎不存在")
    return {
        "success": True,
        "message": "引擎删除成功",
        "engines": [e.to_dict() for e in result.engines],
    }


@router.post("/parser-engine/llm-comparison-config")
def update_llm_comparison_config(
    config: LLMComparisonConfigRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新LLM对比配置"""
    from app.services.llm_engine_config_service import (
        get_llm_engines_config,
        save_llm_engines_config,
    )
    current = get_llm_engines_config(db)
    current.comparison_strategy = config.comparison_strategy
    current.min_consensus_ratio = config.min_consensus_ratio
    save_llm_engines_config(db, current)
    return {
        "success": True,
        "message": "对比配置更新成功",
        "comparison_strategy": current.comparison_strategy,
        "min_consensus_ratio": current.min_consensus_ratio,
    }


@router.post("/parser-engine")
def save_parser_engine_config(
    config: ParserEngineConfig,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """保存解析引擎配置到数据库"""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"[SAVE_PARSER_CONFIG] user={current_user.id} payload={config.model_dump_json()}")
    
    db_config = db.query(GlobalSettings).filter(
        GlobalSettings.settings_key == "parser_engine"
    ).first()
    
    config_dict = {**get_runtime_parser_engine_config(db), **config.model_dump()}
    
    if db_config:
        db_config.settings_value = config_dict
    else:
        db_config = GlobalSettings(
            settings_key="parser_engine",
            settings_value=config_dict,
        )
        db.add(db_config)
    
    db.commit()
    db.refresh(db_config)
    
    return {
        "success": True,
        "message": "配置已保存成功！",
        "config": _mask_parser_engine_config(db_config.settings_value),
    }
