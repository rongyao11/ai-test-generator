from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

import anthropic
from openai import OpenAI

from config import get_settings

_logger = logging.getLogger("ai_client")


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
        _logger.info(f"[Anthropic] Calling model: {self.model}, max_tokens: {max_tokens}")
        start_time = time.time()
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        elapsed = time.time() - start_time
        _logger.info(f"[Anthropic] Response received in {elapsed:.2f}s, content length: {len(response.content) if response.content else 0}")
        for block in response.content:
            if getattr(block, "type", None) == "text":
                text = block.text
                _logger.debug(f"[Anthropic] Response text preview (first 200 chars): {text[:200]}")
                return text
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
        _logger.info(f"[OpenAI] Calling model: {self.model}, max_tokens: {max_tokens}")
        start_time = time.time()
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        elapsed = time.time() - start_time
        content = response.choices[0].message.content or ""
        _logger.info(f"[OpenAI] Response received in {elapsed:.2f}s, content length: {len(content)}")
        _logger.debug(f"[OpenAI] Response text preview (first 200 chars): {content[:200]}")
        return content


_client: AIClient | None = None


def get_ai_client() -> AIClient:
    global _client
    if _client is None:
        settings = get_settings()
        if settings.ai_provider == "openai":
            _logger.info(f"[AI Client] Using OpenAI provider, model: {settings.openai_model}")
            _client = OpenAIClient()
        else:
            _logger.info(f"[AI Client] Using Anthropic provider, model: {settings.anthropic_model}")
            _client = AnthropicClient()
    return _client
