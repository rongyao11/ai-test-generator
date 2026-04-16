from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import anthropic
from openai import OpenAI

from config import get_settings


class AIClient(ABC):
    @abstractmethod
    def generate(self, prompt: str, max_tokens: int) -> str:
        raise NotImplementedError


class AnthropicClient(AIClient):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=120)
        self.model = settings.anthropic_model

    def generate(self, prompt: str, max_tokens: int) -> str:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        for block in response.content:
            if getattr(block, "type", None) == "text":
                return block.text
        return ""


class OpenAIClient(AIClient):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")
        self.client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            timeout=120,
        )
        self.model = settings.openai_model

    def generate(self, prompt: str, max_tokens: int) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content or ""


_client: AIClient | None = None


def get_ai_client() -> AIClient:
    global _client
    if _client is None:
        settings = get_settings()
        if settings.ai_provider == "openai":
            _client = OpenAIClient()
        else:
            _client = AnthropicClient()
    return _client
