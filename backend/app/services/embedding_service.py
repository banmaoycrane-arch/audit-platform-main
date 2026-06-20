import hashlib
import math

import httpx

from app.core.config import get_settings


def _fallback_embed(text: str) -> list[float]:
    """降级方案：基于 token hash 的简单向量化（用于无 AI 配置时）"""
    dimension = get_settings().embedding_dimension
    vector = [0.0] * dimension
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimension
        vector[index] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def embed_text(text: str) -> list[float]:
    """获取文本的 embedding 向量"""
    settings = get_settings()
    
    # 如果未配置 AI，使用降级方案
    if not settings.ai_base_url or not settings.ai_api_key:
        return _fallback_embed(text)
    
    try:
        async def _embed():
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.ai_base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {settings.ai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": settings.ai_model or "text-embedding-3-small",
                        "input": text,
                    },
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
                return data["data"][0]["embedding"]
        
        import asyncio
        return asyncio.run(_embed())
    except Exception:
        # 任何错误都降级到本地 hash 方案
        return _fallback_embed(text)
