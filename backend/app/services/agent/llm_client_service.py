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
    2025-01-20  封装为 LlmClientService 类
"""
import json
from collections.abc import Iterator
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any
from urllib import request

from app.core.config import get_settings


@dataclass
class LLMResult:
    """LLM调用结果。"""
    available: bool
    content: str | None = None
    error: str | None = None
    model: str | None = None
    thinking: str | None = None


class LightweightLLMClient:
    """轻量级LLM客户端，支持OpenAI兼容API和Ollama原生API。"""

    settings: Any
    is_ollama: bool

    def __init__(self, settings: Any | None = None, config: dict[str, Any] | None = None) -> None:
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
                llm_timeout_seconds=int(config.get("llm_timeout_seconds") or 30),
            )
        else:
            self.settings = settings or get_settings()

        # 自动识别是否为Ollama服务
        base_url = self.settings.ai_base_url or ""
        self.is_ollama = ":11434" in base_url or "ollama" in base_url.lower()

    def is_configured(self) -> bool:
        """检查LLM是否已配置。"""
        return bool(self.settings.ai_base_url and self.settings.ai_model)

    def chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        *,
        timeout_seconds: int | None = None,
    ) -> LLMResult:
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
            if timeout_seconds is None:
                configured_timeout = int(getattr(self.settings, "llm_timeout_seconds", 30) or 30)
                # 本地 Ollama + 合规类长 prompt 常超过 2 分钟
                timeout_seconds = max(configured_timeout, 300) if self.is_ollama else max(configured_timeout, 90)
            with request.urlopen(req, timeout=timeout_seconds) as response:
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

    def iter_chat_stream(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        *,
        timeout_seconds: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        """
        流式调用 LLM（主要用于 Ollama 本地模型），逐块产出思索/回复文本。

        Yields:
            {"channel": "thinking"|"content", "delta": str, "text": str}
            结束时 yield {"channel": "done", "content": str, "thinking": str}
            失败时 yield {"channel": "error", "error": str}
        """
        if not self.is_configured():
            yield {"channel": "error", "error": "LLM 未配置"}
            return

        if timeout_seconds is None:
            configured_timeout = int(getattr(self.settings, "llm_timeout_seconds", 30) or 30)
            timeout_seconds = max(configured_timeout, 300) if self.is_ollama else max(configured_timeout, 90)

        if not self.is_ollama:
            result = self.chat(messages, temperature, timeout_seconds=timeout_seconds)
            if not result.available:
                yield {"channel": "error", "error": result.error or "LLM 调用失败"}
                return
            if result.content:
                yield {"channel": "content", "delta": result.content, "text": result.content}
            yield {
                "channel": "done",
                "content": result.content or "",
                "thinking": result.thinking or "",
            }
            return

        base_url = self.settings.ai_base_url.rstrip("/").rstrip("/v1")
        url = f"{base_url}/api/chat"
        body = {
            "model": self.settings.ai_model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature},
        }
        headers = {"Content-Type": "application/json"}
        if self.settings.ai_api_key:
            headers["Authorization"] = f"Bearer {self.settings.ai_api_key}"

        full_content = ""
        full_thinking = ""
        try:
            payload = json.dumps(body).encode("utf-8")
            req = request.Request(url, data=payload, headers=headers, method="POST")
            with request.urlopen(req, timeout=timeout_seconds) as response:
                buffer = ""
                while True:
                    raw = response.read(4096)
                    if not raw:
                        break
                    buffer += raw.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        message = data.get("message") or {}
                        thinking_delta = str(message.get("thinking") or "")
                        content_delta = str(message.get("content") or "")
                        if thinking_delta:
                            full_thinking += thinking_delta
                            yield {
                                "channel": "thinking",
                                "delta": thinking_delta,
                                "text": full_thinking,
                            }
                        if content_delta:
                            full_content += content_delta
                            yield {
                                "channel": "content",
                                "delta": content_delta,
                                "text": full_content,
                            }
                        if data.get("done"):
                            yield {
                                "channel": "done",
                                "content": full_content,
                                "thinking": full_thinking,
                            }
                            return
            yield {
                "channel": "done",
                "content": full_content,
                "thinking": full_thinking,
            }
        except Exception as exc:
            yield {"channel": "error", "error": str(exc)}


class LlmClientService:
    """LLM客户端服务包装类"""
    
    def __init__(self, settings: Any | None = None, config: dict[str, Any] | None = None) -> None:
        self.client = LightweightLLMClient(settings, config)
    
    def is_configured(self) -> bool:
        return self.client.is_configured()
    
    def chat(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        *,
        timeout_seconds: int | None = None,
    ) -> LLMResult:
        return self.client.chat(messages, temperature, timeout_seconds=timeout_seconds)

    def iter_chat_stream(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.2,
        *,
        timeout_seconds: int | None = None,
    ) -> Iterator[dict[str, Any]]:
        return self.client.iter_chat_stream(messages, temperature, timeout_seconds=timeout_seconds)
    
    @property
    def is_ollama(self) -> bool:
        return self.client.is_ollama
