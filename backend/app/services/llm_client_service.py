import json
from dataclasses import dataclass
from urllib import request

from app.core.config import get_settings


@dataclass
class LLMResult:
    available: bool
    content: str | None = None
    error: str | None = None
    model: str | None = None


class LightweightLLMClient:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    def is_configured(self) -> bool:
        return bool(self.settings.ai_base_url and self.settings.ai_model)

    def chat(self, messages: list[dict], temperature: float = 0.2) -> LLMResult:
        if not self.is_configured():
            return LLMResult(available=False, error="LLM 未配置", model=self.settings.ai_model or None)

        url = f"{self.settings.ai_base_url.rstrip('/')}/chat/completions"
        body = {
            "model": self.settings.ai_model,
            "messages": messages,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        headers = {"Content-Type": "application/json"}
        if self.settings.ai_api_key:
            headers["Authorization"] = f"Bearer {self.settings.ai_api_key}"

        try:
            payload = json.dumps(body).encode("utf-8")
            req = request.Request(url, data=payload, headers=headers, method="POST")
            with request.urlopen(req, timeout=8) as response:
                data = json.loads(response.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            return LLMResult(available=True, content=content, model=self.settings.ai_model)
        except Exception as exc:
            return LLMResult(available=False, error=str(exc), model=self.settings.ai_model)
