# -*- coding: utf-8 -*-
"""
模块功能：多LLM引擎配置管理服务
业务场景：管理多个LLM引擎的配置，支持增删改查，支持多供应商多模型
政策依据：企业级AI应用多模型对比与选型最佳实践
输入数据：LLM引擎配置参数（供应商、URL、模型、密钥、权重等）
输出结果：配置持久化到数据库，支持动态读取
创建日期：2026-06-27
更新记录：
    2026-06-27  初始创建，支持多LLM引擎配置管理
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models.global_settings import GlobalSettings


SETTINGS_KEY = "parser_engine_llm_engines"


@dataclass
class LLMEngineConfig:
    """LLM引擎配置。"""

    id: str
    name: str
    provider: str
    base_url: str
    model: str
    api_key: str = ""
    weight: float = 0.3
    enabled: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LLMEngineConfig":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            provider=data.get("provider", "openai-compatible"),
            base_url=data.get("base_url", ""),
            model=data.get("model", ""),
            api_key=data.get("api_key", ""),
            weight=float(data.get("weight", 0.3)),
            enabled=bool(data.get("enabled", True)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "provider": self.provider,
            "base_url": self.base_url,
            "model": self.model,
            "api_key": self.api_key,
            "weight": self.weight,
            "enabled": self.enabled,
        }


@dataclass
class LLMEngineComparisonConfig:
    """LLM引擎对比配置。"""

    engines: list[LLMEngineConfig]
    comparison_strategy: str = "field_consensus"
    min_consensus_ratio: float = 0.5

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LLMEngineComparisonConfig":
        engines_data = data.get("engines", [])
        engines = [LLMEngineConfig.from_dict(e) for e in engines_data]
        return cls(
            engines=engines,
            comparison_strategy=data.get("comparison_strategy", "field_consensus"),
            min_consensus_ratio=float(data.get("min_consensus_ratio", 0.5)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "engines": [e.to_dict() for e in self.engines],
            "comparison_strategy": self.comparison_strategy,
            "min_consensus_ratio": self.min_consensus_ratio,
        }

    def get_enabled_engines(self) -> list[LLMEngineConfig]:
        """获取启用的引擎列表。"""
        return [e for e in self.engines if e.enabled]


def get_llm_engines_config(db: Session) -> LLMEngineComparisonConfig:
    """
    获取多LLM引擎配置

    功能描述：从数据库读取多LLM引擎配置
    业务逻辑：从global_settings表读取配置，不存在则返回默认空配置

    Args:
        db: 数据库会话

    Returns:
        LLMEngineComparisonConfig: 多LLM引擎对比配置
    """
    setting = db.query(GlobalSettings).filter(
        GlobalSettings.settings_key == SETTINGS_KEY
    ).first()

    if setting and setting.settings_value:
        return LLMEngineComparisonConfig.from_dict(setting.settings_value)

    return LLMEngineComparisonConfig(engines=[])


def save_llm_engines_config(db: Session, config: LLMEngineComparisonConfig) -> None:
    """
    保存多LLM引擎配置

    功能描述：将多LLM引擎配置保存到数据库
    业务逻辑：upsert方式，存在则更新，不存在则插入

    Args:
        db: 数据库会话
        config: 多LLM引擎对比配置
    """
    setting = db.query(GlobalSettings).filter(
        GlobalSettings.settings_key == SETTINGS_KEY
    ).first()

    if setting:
        setting.settings_value = config.to_dict()
    else:
        setting = GlobalSettings(
            settings_key=SETTINGS_KEY,
            settings_value=config.to_dict(),
        )
        db.add(setting)

    db.commit()


def add_llm_engine(db: Session, engine: LLMEngineConfig) -> LLMEngineComparisonConfig:
    """
    添加一个LLM引擎

    功能描述：向配置中添加一个新的LLM引擎
    业务逻辑：读取现有配置，添加新引擎，保存到数据库

    Args:
        db: 数据库会话
        engine: 新的LLM引擎配置

    Returns:
        LLMEngineComparisonConfig: 更新后的配置
    """
    config = get_llm_engines_config(db)

    if not engine.id:
        import time
        engine.id = f"engine_{int(time.time())}"

    config.engines.append(engine)
    save_llm_engines_config(db, config)
    return config


def update_llm_engine(db: Session, engine_id: str, engine_data: dict[str, Any]) -> LLMEngineComparisonConfig | None:
    """
    更新一个LLM引擎

    功能描述：更新指定ID的LLM引擎配置
    业务逻辑：读取现有配置，找到对应引擎，更新字段，保存到数据库

    Args:
        db: 数据库会话
        engine_id: 引擎ID
        engine_data: 更新的字段

    Returns:
        LLMEngineComparisonConfig | None: 更新后的配置，找不到返回None
    """
    config = get_llm_engines_config(db)

    found = False
    for engine in config.engines:
        if engine.id == engine_id:
            for key, value in engine_data.items():
                if hasattr(engine, key):
                    setattr(engine, key, value)
            found = True
            break

    if not found:
        return None

    save_llm_engines_config(db, config)
    return config


def delete_llm_engine(db: Session, engine_id: str) -> LLMEngineComparisonConfig | None:
    """
    删除一个LLM引擎

    功能描述：删除指定ID的LLM引擎
    业务逻辑：读取现有配置，删除对应引擎，保存到数据库

    Args:
        db: 数据库会话
        engine_id: 引擎ID

    Returns:
        LLMEngineComparisonConfig | None: 更新后的配置，找不到返回None
    """
    config = get_llm_engines_config(db)

    original_len = len(config.engines)
    config.engines = [e for e in config.engines if e.id != engine_id]

    if len(config.engines) == original_len:
        return None

    save_llm_engines_config(db, config)
    return config
