from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.db.session import get_db
from app.models.global_settings import GlobalSettings
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/config", tags=["config"])


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


class TestConnectionRequest(BaseModel):
    ai_base_url: str
    ai_model: str
    ai_api_key: str | None = None


@router.get("/parser-engine", response_model=ParserEngineConfig)
def get_parser_engine_config(db: Session = Depends(get_db)):
    """获取当前解析引擎配置"""
    settings = get_settings()
    
    db_config = db.query(GlobalSettings).filter(
        GlobalSettings.settings_key == "parser_engine"
    ).first()
    
    if db_config and db_config.settings_value:
        return db_config.settings_value
    
    return {
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
    }


@router.post("/parser-engine/test-connection")
def test_ai_connection(request: TestConnectionRequest):
    """
    测试AI模型连接是否可用
    
    自动识别服务类型：
    - Ollama（端口11434）：使用原生 /api/chat 端点
    - 其他 OpenAI 兼容服务：使用 /v1/chat/completions 端点
    """
    import json
    import time
    from urllib import request as url_request
    
    base_url = request.ai_base_url.rstrip("/").rstrip("/v1")
    
    # 判断是否为 Ollama 服务（通过端口或 URL 特征）
    is_ollama = ":11434" in base_url or "ollama" in base_url.lower()
    
    headers = {"Content-Type": "application/json"}
    if request.ai_api_key:
        headers["Authorization"] = f"Bearer {request.ai_api_key}"
    
    try:
        start_time = time.time()
        
        if is_ollama:
            # Ollama 原生 API: /api/chat
            url = f"{base_url}/api/chat"
            body = {
                "model": request.ai_model,
                "messages": [{"role": "user", "content": "请用一个字回答：测"}],
                "stream": False,
            }
        else:
            # OpenAI 兼容 API: /v1/chat/completions
            url = f"{base_url}/v1/chat/completions"
            body = {
                "model": request.ai_model,
                "messages": [{"role": "user", "content": "请用一个字回答：测"}],
                "temperature": 0.0,
                "max_tokens": 5,
            }
        
        payload = json.dumps(body).encode("utf-8")
        req = url_request.Request(url, data=payload, headers=headers, method="POST")
        with url_request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        response_time = round(time.time() - start_time, 2)
        
        # 处理不同 API 的返回格式
        content = None
        usage = {}
        
        if is_ollama:
            # Ollama 原生 API 返回格式
            if "message" in data:
                content = data["message"].get("content", "").strip()
                # Ollama 使用不同的统计字段
                usage = {
                    "prompt_tokens": data.get("prompt_eval_count"),
                    "completion_tokens": data.get("eval_count"),
                    "total_tokens": (data.get("prompt_eval_count") or 0) + (data.get("eval_count") or 0),
                }
        else:
            # OpenAI 兼容 API 返回格式
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"].strip()
                usage = data.get("usage", {})
        
        if content:
            return {
                "success": True,
                "message": f"连接成功！模型已正常响应",
                "model": request.ai_model,
                "base_url": request.ai_base_url,
                "api_type": "ollama-native" if is_ollama else "openai-compatible",
                "response_content": content,
                "response_time_ms": response_time * 1000,
                "usage": {
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                },
            }
        else:
            return {"success": False, "message": "连接成功但返回格式异常", "raw_response": str(data)}
            
    except Exception as e:
        return {
            "success": False,
            "message": f"连接失败: {str(e)}",
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


@router.post("/parser-engine")
def save_parser_engine_config(
    config: ParserEngineConfig,
    db: Session = Depends(get_db),
):
    """保存解析引擎配置到数据库"""
    db_config = db.query(GlobalSettings).filter(
        GlobalSettings.settings_key == "parser_engine"
    ).first()
    
    config_dict = config.dict()
    
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
        "config": db_config.settings_value,
    }
