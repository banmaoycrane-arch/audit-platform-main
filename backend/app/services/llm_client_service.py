# -*- coding: utf-8 -*-
"""
模块功能：轻量级LLM客户端
业务场景：调用各种LLM API进行文本生成、解析等
政策依据：无
输入数据：提示词、模型配置
输出结果：LLM生成的文本内容
创建日期：2026-06-26
更新记录：
    2026-06-27  增加Ollama原生API支持，自动识别服务类型
"""
import json
from dataclasses import dataclass
from types import SimpleNamespace
from urllib import request

from app.core.config import get_settings


@dataclass
class LLMResult:
    """LLM调用结果。"""
    available: bool
    content: str | None = None
    error: str | None = None
    model: str | None = None


class LightweightLLMClient:
    """轻量级LLM客户端，支持OpenAI兼容API和Ollama原生API。"""

    def __init__(self, settings=None, config: dict | None = None):
        """
        LLM客户端初始化

        功能描述：支持从settings对象或字典配置初始化
        业务逻辑：
            - 优先使用传入的config字典
            - 其次使用传入的settings对象
            - 最后使用全局settings
            - 自动识别是否为Ollama服务

        Args:
            settings: settings对象（可选）
            config: 字典配置，包含ai_base_url, ai_model, ai_api_key等（可选）
        """
        if config:
            self.settings = SimpleNamespace(
                ai_base_url=config.get("ai_base_url", ""),
                ai_model=config.get("ai_model", ""),
                ai_api_key=config.get("ai_api_key", None),
            )
        else:
            self.settings = settings or get_settings()

        # 自动识别是否为Ollama服务
        base_url = self.settings.ai_base_url or ""
        self.is_ollama = ":11434" in base_url or "ollama" in base_url.lower()

    def is_configured(self) -> bool:
        """检查LLM是否已配置。"""
        return bool(self.settings.ai_base_url and self.settings.ai_model)

    def chat(self, messages: list[dict], temperature: float = 0.2) -> LLMResult:
        """
        调用LLM聊天接口

        功能描述：发送消息到LLM并获取回复
        业务逻辑：
            - 自动识别Ollama服务，使用原生/api/chat端点
            - 其他服务使用OpenAI兼容的/v1/chat/completions端点
            - 统一处理返回格式

        Args:
            messages: 聊天消息列表
            temperature: 温度参数

        Returns:
            LLMResult: 调用结果
        """
        if not self.is_configured():
            return LLMResult(available=False, error="LLM 未配置", model=self.settings.ai_model or None)

        base_url = self.settings.ai_base_url.rstrip("/").rstrip("/v1")
        headers = {"Content-Type": "application/json"}
        if self.settings.ai_api_key:
            headers["Authorization"] = f"Bearer {self.settings.ai_api_key}"

        try:
            if self.is_ollama:
                # Ollama 原生 API: /api/chat
                url = f"{base_url}/api/chat"
                body = {
                    "model": self.settings.ai_model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                    },
                }
            else:
                # OpenAI 兼容 API: /v1/chat/completions
                url = f"{base_url}/v1/chat/completions"
                body = {
                    "model": self.settings.ai_model,
                    "messages": messages,
                    "temperature": temperature,
                    "response_format": {"type": "json_object"},
                }

            payload = json.dumps(body).encode("utf-8")
            req = request.Request(url, data=payload, headers=headers, method="POST")
            with request.urlopen(req, timeout=60) as response:
                data = json.loads(response.read().decode("utf-8"))

            # 解析返回内容
            content = None
            if self.is_ollama:
                # Ollama 原生格式
                if "message" in data:
                    content = data["message"].get("content", "")
            else:
                # OpenAI 兼容格式
                if "choices" in data and len(data["choices"]) > 0:
                    content = data["choices"][0]["message"].get("content", "")

            if content is not None:
                return LLMResult(available=True, content=content, model=self.settings.ai_model)
            else:
                return LLMResult(
                    available=False,
                    error=f"返回格式异常: {str(data)[:200]}",
                    model=self.settings.ai_model,
                )

        except Exception as exc:
            return LLMResult(available=False, error=str(exc), model=self.settings.ai_model)
