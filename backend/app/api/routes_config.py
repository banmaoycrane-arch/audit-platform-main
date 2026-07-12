from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.global_settings import GlobalSettings
from app.models.user import User
from app.services.doc_parsing.parser_engine.config_service import (
    get_runtime_parser_engine_config,
    is_masked_api_key,
    normalize_parser_engine_config,
    resolve_api_key_for_use,
    resolve_effective_llm_config,
    _probe_openai_compatible,
)
from app.models.ledger import Ledger
from app.services.shared import ledger_management_service
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/config", tags=["config"])


def _require_ledger_access(db: Session, current_user: User, ledger_id: int) -> Ledger:
    """确认账簿存在且当前用户有权访问，避免 FK/脏数据导致 500。"""
    ledger = db.query(Ledger).filter(Ledger.id == ledger_id).first()
    if ledger is None:
        raise HTTPException(
            status_code=404,
            detail={"message": f"账簿 {ledger_id} 不存在，请重新选择账簿"},
        )
    if not ledger_management_service.user_has_ledger_access(db, current_user.id, ledger_id):
        raise HTTPException(
            status_code=403,
            detail={"message": f"无权访问账簿 {ledger_id}，请联系账簿管理员授权"},
        )
    return ledger


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
    if masked.get("ai_cloud_api_key"):
        masked["ai_cloud_api_key"] = _mask_api_key(str(masked["ai_cloud_api_key"]))
    if masked.get("ai_local_api_key"):
        masked["ai_local_api_key"] = _mask_api_key(str(masked["ai_local_api_key"]))
    return masked


class ParserEngineConfig(BaseModel):
    ai_provider: str
    ai_base_url: str
    ai_model: str
    ai_reasoning_model: str = ""
    ai_api_key: str | None = None
    ai_routing_mode: str = "manual"
    ai_local_base_url: str = ""
    ai_local_model: str = ""
    ai_local_api_key: str | None = None
    ai_cloud_base_url: str = ""
    ai_cloud_model: str = ""
    ai_cloud_api_key: str | None = None
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
def get_parser_engine_config(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """获取当前解析引擎配置（含解析模型与推理模型）。"""
    return _mask_parser_engine_config(get_runtime_parser_engine_config(db))


@router.post("/parser-engine/test-connection")
def test_ai_connection(
    request: TestConnectionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    测试AI模型连接是否可用。

    连接测试只做轻量级探活和模型存在性检查，避免触发 Ollama 加载大模型导致长时间无响应。
    """
    import json
    import time
    from urllib import request as url_request
    from urllib.error import HTTPError, URLError

    stored = get_runtime_parser_engine_config(db)
    api_key = resolve_api_key_for_use(request.ai_api_key, stored.get("ai_api_key"))

    normalized_input_url = request.ai_base_url.rstrip("/")
    ollama_root_url = normalized_input_url[:-3] if normalized_input_url.endswith("/v1") else normalized_input_url
    is_ollama = ":11434" in normalized_input_url or "ollama" in normalized_input_url.lower()

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    def fetch_json(url: str, timeout: int = 5) -> dict[str, Any]:
        req = url_request.Request(url, headers=headers, method="GET")
        with url_request.urlopen(req, timeout=timeout) as response:
            result: dict[str, Any] = json.loads(response.read().decode("utf-8"))
            return result

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

        ok, message, available_models, elapsed_ms = _probe_openai_compatible(
            request.ai_base_url,
            request.ai_model,
            api_key,
        )
        if ok:
            return {
                "success": True,
                "message": message,
                "model": request.ai_model,
                "base_url": request.ai_base_url,
                "api_type": "openai-compatible",
                "response_content": "探活成功",
                "response_time_ms": elapsed_ms,
                "available_models": available_models or None,
            }
        return {
            "success": False,
            "message": message,
            "model": request.ai_model,
            "base_url": request.ai_base_url,
            "api_type": "openai-compatible",
            "available_models": available_models or None,
            "response_time_ms": elapsed_ms,
        }
    except Exception as exc:
        errors.append(f"OpenAI兼容探活失败: {exc}")
        return {
            "success": False,
            "message": "连接失败: " + "; ".join(errors),
            "model": request.ai_model,
            "base_url": request.ai_base_url,
        }


@router.get("/provider-options")
def get_provider_options() -> dict[str, Any]:
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
def get_ollama_models(base_url: str = "http://localhost:11434") -> dict[str, Any]:
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
def get_llm_engines(db: Session = Depends(get_db)) -> dict[str, Any]:
    """获取多LLM引擎配置列表"""
    from app.services.agent.llm_engine_config_service import get_llm_engines_config
    config = get_llm_engines_config(db)
    return {
        "success": True,
        "engines": [e.to_dict() for e in config.engines],
        "comparison_strategy": config.comparison_strategy,
        "min_consensus_ratio": config.min_consensus_ratio,
    }


@router.post("/parser-engine/llm-engines")
def add_llm_engine(engine: LLMEngineCreateRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """添加一个LLM引擎"""
    from app.services.agent.llm_engine_config_service import (
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
def update_llm_engine(engine_id: str, engine: LLMEngineUpdateRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    """更新一个LLM引擎"""
    from app.services.agent.llm_engine_config_service import update_llm_engine
    result = update_llm_engine(db, engine_id, engine.model_dump(exclude_unset=True))
    if result is None:
        raise HTTPException(status_code=404, detail="引擎不存在")
    return {
        "success": True,
        "message": "引擎更新成功",
        "engines": [e.to_dict() for e in result.engines],
    }


@router.delete("/parser-engine/llm-engines/{engine_id}")
def delete_llm_engine(engine_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    """删除一个LLM引擎"""
    from app.services.agent.llm_engine_config_service import delete_llm_engine
    result = delete_llm_engine(db, engine_id)
    if result is None:
        raise HTTPException(status_code=404, detail="引擎不存在")
    return {
        "success": True,
        "message": "引擎删除成功",
        "engines": [e.to_dict() for e in result.engines],
    }


@router.post("/parser-engine/llm-comparison-config")
def update_llm_comparison_config(config: LLMComparisonConfigRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """更新LLM对比配置"""
    from app.services.agent.llm_engine_config_service import (
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
def save_parser_engine_config(config: ParserEngineConfig, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """保存解析引擎配置到数据库"""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"[SAVE_PARSER_CONFIG] user={current_user.id} payload={config.model_dump_json()}")
    
    db_config = db.query(GlobalSettings).filter(
        GlobalSettings.settings_key == "parser_engine"
    ).first()
    
    existing = get_runtime_parser_engine_config(db)
    incoming = config.model_dump()
    incoming["ai_api_key"] = resolve_api_key_for_use(incoming.get("ai_api_key"), existing.get("ai_api_key"))
    incoming["ai_cloud_api_key"] = resolve_api_key_for_use(
        incoming.get("ai_cloud_api_key"),
        existing.get("ai_cloud_api_key"),
    )
    incoming["ai_local_api_key"] = resolve_api_key_for_use(
        incoming.get("ai_local_api_key"),
        existing.get("ai_local_api_key"),
    )

    config_dict = normalize_parser_engine_config(
        {
            **existing,
            **incoming,
            "ai_reasoning_model": (config.ai_reasoning_model or "").strip(),
            "ai_model": (config.ai_model or "").strip(),
        }
    )
    
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


class AccountTagConfigRequest(BaseModel):
    version: str
    mandatory_hierarchical_accounts: list[str] = []
    mandatory_hierarchical_keywords: list[str] = []
    account_code_tag_category: dict[str, str] = {}
    account_name_tag_category: dict[str, str] = {}
    auxiliary_keywords: dict[str, list[str]] = {}


@router.get("/account-tag-rules")
def get_account_tag_rules(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """获取科目与标签解析规则配置"""
    from app.config.account_tag_config import load_account_tag_config

    config = load_account_tag_config(db)
    return {
        "success": True,
        "config": {
            "version": config.version,
            "mandatory_hierarchical_accounts": list(config.mandatory_hierarchical_accounts),
            "mandatory_hierarchical_keywords": list(config.mandatory_hierarchical_keywords),
            "account_code_tag_category": config.account_code_tag_category,
            "account_name_tag_category": config.account_name_tag_category,
            "auxiliary_keywords": config.auxiliary_keywords,
        },
    }


@router.post("/account-tag-rules")
def save_account_tag_rules(config: AccountTagConfigRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """保存科目与标签解析规则配置到数据库"""
    from app.config.account_tag_config import AccountTagConfig, save_account_tag_config_to_db

    account_tag_config = AccountTagConfig(
        version=config.version,
        mandatory_hierarchical_accounts=set(config.mandatory_hierarchical_accounts),
        mandatory_hierarchical_keywords=set(config.mandatory_hierarchical_keywords),
        account_code_tag_category=config.account_code_tag_category,
        account_name_tag_category=config.account_name_tag_category,
        auxiliary_keywords=config.auxiliary_keywords,
    )

    save_account_tag_config_to_db(db, account_tag_config, user_id=current_user.id)

    return {
        "success": True,
        "message": "科目与标签解析规则配置已保存！",
        "config": {
            "version": account_tag_config.version,
            "mandatory_hierarchical_accounts": list(account_tag_config.mandatory_hierarchical_accounts),
            "mandatory_hierarchical_keywords": list(account_tag_config.mandatory_hierarchical_keywords),
            "account_code_tag_category": account_tag_config.account_code_tag_category,
            "account_name_tag_category": account_tag_config.account_name_tag_category,
            "auxiliary_keywords": account_tag_config.auxiliary_keywords,
        },
    }


@router.post("/account-tag-rules/reset")
def reset_account_tag_rules(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """重置科目与标签解析规则配置为默认值（从YAML文件加载）"""
    from app.config.account_tag_config import load_account_tag_config_from_file, CONFIG_KEY
    from app.models.global_settings import GlobalSettings

    config = load_account_tag_config_from_file()

    db_config = db.query(GlobalSettings).filter(
        GlobalSettings.settings_key == CONFIG_KEY
    ).first()
    if db_config:
        db.delete(db_config)
        db.commit()

    return {
        "success": True,
        "message": "科目与标签解析规则配置已重置为默认值！",
        "config": {
            "version": config.version,
            "mandatory_hierarchical_accounts": list(config.mandatory_hierarchical_accounts),
            "mandatory_hierarchical_keywords": list(config.mandatory_hierarchical_keywords),
            "account_code_tag_category": config.account_code_tag_category,
            "account_name_tag_category": config.account_name_tag_category,
            "auxiliary_keywords": config.auxiliary_keywords,
        },
    }


def _account_tag_config_payload(config) -> dict[str, Any]:
    return {
        "version": config.version,
        "mandatory_hierarchical_accounts": list(config.mandatory_hierarchical_accounts),
        "mandatory_hierarchical_keywords": list(config.mandatory_hierarchical_keywords),
        "account_code_tag_category": config.account_code_tag_category,
        "account_name_tag_category": config.account_name_tag_category,
        "auxiliary_keywords": config.auxiliary_keywords,
    }


@router.get("/ledgers/{ledger_id}/account-tag-rules")
def get_ledger_account_tag_rules(
    ledger_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """获取账簿级解析映射（平台默认 + 账簿覆盖合并后的有效配置）。"""
    from app.config.account_tag_config import (
        load_account_tag_config,
        load_ledger_account_tag_override,
    )

    config = load_account_tag_config(db, ledger_id=ledger_id)
    override = load_ledger_account_tag_override(db, ledger_id)
    return {
        "success": True,
        "scope": "ledger",
        "ledger_id": ledger_id,
        "has_ledger_override": override is not None,
        "config": _account_tag_config_payload(config),
        "ledger_override": override,
    }


@router.post("/ledgers/{ledger_id}/account-tag-rules")
def save_ledger_account_tag_rules(
    ledger_id: int,
    config: AccountTagConfigRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """保存账簿级解析映射覆盖（不影响平台全局默认）。"""
    from app.config.account_tag_config import AccountTagConfig, save_ledger_account_tag_override

    account_tag_config = AccountTagConfig(
        version=config.version,
        mandatory_hierarchical_accounts=set(config.mandatory_hierarchical_accounts),
        mandatory_hierarchical_keywords=set(config.mandatory_hierarchical_keywords),
        account_code_tag_category=config.account_code_tag_category,
        account_name_tag_category=config.account_name_tag_category,
        auxiliary_keywords=config.auxiliary_keywords,
    )
    save_ledger_account_tag_override(db, ledger_id, account_tag_config)
    from app.services.doc_parsing.dimension_readiness_service import acknowledge_tag_rules_reviewed

    acknowledge_tag_rules_reviewed(db, ledger_id, reviewed_by=current_user.id)
    db.commit()
    return {
        "success": True,
        "message": "账簿级解析映射已保存，本账簿下一批导入将优先使用此配置。",
        "config": _account_tag_config_payload(account_tag_config),
        "has_ledger_override": True,
    }


@router.get("/ledgers/{ledger_id}/dimension-readiness")
def get_ledger_dimension_readiness(
    ledger_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """评估本账簿是否已完成 tag 规则审阅，可否进行序时簿结构化导入。"""
    from app.services.doc_parsing.dimension_readiness_service import assess_ledger_dimension_readiness

    _require_ledger_access(db, current_user, ledger_id)
    return assess_ledger_dimension_readiness(db, ledger_id)


@router.post("/ledgers/{ledger_id}/dimension-readiness/acknowledge")
def acknowledge_ledger_dimension_readiness(
    ledger_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """确认本账簿 tag 规则与维度分类已审阅，允许结构化导入。"""
    from app.services.doc_parsing.dimension_readiness_service import acknowledge_tag_rules_reviewed

    _require_ledger_access(db, current_user, ledger_id)
    try:
        result = acknowledge_tag_rules_reviewed(db, ledger_id, reviewed_by=current_user.id)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail={"message": f"确认维度规则审阅失败：{exc}"},
        ) from exc
    return {"success": True, **result}


@router.post("/ledgers/{ledger_id}/account-tag-rules/reset")
def reset_ledger_account_tag_rules(
    ledger_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """清除账簿级解析映射覆盖，恢复使用平台默认。"""
    from app.config.account_tag_config import clear_ledger_account_tag_override, load_account_tag_config

    clear_ledger_account_tag_override(db, ledger_id)
    config = load_account_tag_config(db, ledger_id=ledger_id)
    return {
        "success": True,
        "message": "已清除账簿级覆盖，恢复使用平台默认解析映射。",
        "config": _account_tag_config_payload(config),
        "has_ledger_override": False,
    }
