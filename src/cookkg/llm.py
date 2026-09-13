"""Small OpenAI-compatible LLM boundary with no provider-specific dependency."""

import json
import os
import urllib.error
import urllib.request
from typing import Protocol


class LlmClient(Protocol):
    def generate(self, messages: list[dict[str, str]]) -> str: ...


class LlmUnavailableError(RuntimeError):
    pass


class OpenAICompatibleLlm:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 30):
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def generate(self, messages: list[dict[str, str]]) -> str:
        payload = json.dumps(
            {"model": self.model, "messages": messages, "temperature": 0},
            ensure_ascii=False,
        ).encode("utf-8")
        request = urllib.request.Request(
            self.url,
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
            return str(body["choices"][0]["message"]["content"])
        except (OSError, KeyError, IndexError, ValueError, urllib.error.URLError) as error:
            raise LlmUnavailableError("问答模型调用失败") from error


def llm_from_env() -> LlmClient | None:
    base_url = os.getenv("LLM_BASE_URL", "").strip()
    api_key = os.getenv("LLM_API_KEY", "").strip()
    model = os.getenv("LLM_MODEL", "").strip()
    if not base_url or not model:
        return None
    return OpenAICompatibleLlm(base_url, api_key or "local", model)
