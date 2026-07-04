# -*- coding: utf-8 -*-
"""
模块功能：AI客户端服务
业务场景：调用大模型生成文本，支持异步和同步调用
政策依据：无
输入数据：消息列表、模型名称
输出结果：AI生成的文本内容
创建日期：2026-06-01
更新记录：
    2025-01-20  封装为 AIClientService 类
"""
from typing import Any, Optional

import httpx

from app.core.config import get_settings


class AIClient:
    """OpenAI 兼容 API 客户端"""
    
    def __init__(self) -> None:
        self.settings = get_settings()
        self._enabled = bool(self.settings.ai_base_url and self.settings.ai_api_key)
    
    @property
    def enabled(self) -> bool:
        return self._enabled
    
    async def chat_completion(self, messages: list[dict[str, Any]], model: Optional[str] = None) -> str:
        """调用大模型生成文本"""
        if not self.enabled:
            raise RuntimeError("AI 服务未配置")
        
        url = f"{self.settings.ai_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.ai_api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": model or self.settings.ai_model or "gpt-4o-mini",
            "messages": messages,
            "temperature": 0.7,
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=data)
            response.raise_for_status()
            result: dict[str, Any] = response.json()
            content = result["choices"][0]["message"]["content"]
            return str(content)
    
    def sync_chat_completion(self, messages: list[dict[str, Any]], model: Optional[str] = None) -> str:
        """同步版本的 chat_completion"""
        if not self.enabled:
            raise RuntimeError("AI 服务未配置")
        
        import asyncio
        return asyncio.run(self.chat_completion(messages, model))


class AIClientService:
    """AI客户端服务包装类"""
    
    def __init__(self) -> None:
        self.client = AIClient()
    
    @property
    def enabled(self) -> bool:
        return self.client.enabled
    
    async def chat_completion(self, messages: list[dict[str, Any]], model: Optional[str] = None) -> str:
        return await self.client.chat_completion(messages, model)
    
    def sync_chat_completion(self, messages: list[dict[str, Any]], model: Optional[str] = None) -> str:
        return self.client.sync_chat_completion(messages, model)


def get_ai_client() -> AIClient:
    """获取 AI 客户端实例"""
    return AIClient()
