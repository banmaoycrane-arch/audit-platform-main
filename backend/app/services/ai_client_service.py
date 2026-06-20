from typing import Optional

import httpx

from app.core.config import get_settings


class AIClient:
    """OpenAI 兼容 API 客户端"""
    
    def __init__(self):
        self.settings = get_settings()
        self._enabled = bool(self.settings.ai_base_url and self.settings.ai_api_key)
    
    @property
    def enabled(self) -> bool:
        return self._enabled
    
    async def chat_completion(self, messages: list[dict], model: Optional[str] = None) -> str:
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
            result = response.json()
            return result["choices"][0]["message"]["content"]
    
    def sync_chat_completion(self, messages: list[dict], model: Optional[str] = None) -> str:
        """同步版本的 chat_completion"""
        if not self.enabled:
            raise RuntimeError("AI 服务未配置")
        
        import asyncio
        return asyncio.run(self.chat_completion(messages, model))


def get_ai_client() -> AIClient:
    """获取 AI 客户端实例"""
    return AIClient()
