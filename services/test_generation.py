from __future__ import annotations

import json
import time

from config import get_settings
from models.schemas import AnalysisArtifact, GeneratedTestCase, GenerationPayload, GenerationResponse, RetrievedContextItem
from prompts.generation_prompt import build_generation_prompt
from pydantic import ValidationError
from services.ai_client import get_ai_client


class TestGenerationService:
    def __init__(self) -> None:
        get_settings()  # 触发配置校验

    def generate(
        self,
        artifact: AnalysisArtifact,
        retrieved_context: list[RetrievedContextItem],
    ) -> GenerationResponse:
        payload = self._call_with_retries(artifact, retrieved_context)
        validated = GenerationPayload.model_validate(payload)
        cases = [self._ensure_source_refs(case) for case in validated.test_cases]
        return GenerationResponse(
            document_id=artifact.document_id,
            test_cases=cases,
            retrieved_context_count=len(retrieved_context),
        )

    def _call_with_retries(
        self,
        artifact: AnalysisArtifact,
        retrieved_context: list[RetrievedContextItem],
    ) -> dict:
        prompt = build_generation_prompt(artifact, retrieved_context)
        last_error: Exception | None = None
        settings = get_settings()
        for attempt in range(1, settings.max_retries + 1):
            try:
                client = get_ai_client()
                raw = client.generate(prompt, max_tokens=16000)
                parsed = self._parse_response(raw)
                GenerationPayload.model_validate(parsed)
                return parsed
            except Exception as exc:
                last_error = exc
                if attempt == settings.max_retries:
                    break
                time.sleep(2 ** (attempt - 1))
        raise RuntimeError("AI test generation failed after retries") from last_error

    def _parse_response(self, raw: str) -> dict:
        raw = raw.strip()
        if not raw:
            raise ValueError("LLM returned empty response")
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            # 尝试提取 JSON 对象
            extracted = self._extract_json_object(raw)
            if not extracted or extracted == "{}":
                raise ValueError(f"LLM returned non-JSON content (first 200 chars): {raw[:200]}") from exc
            return json.loads(extracted)

    def _extract_json_object(self, raw: str) -> str:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or start >= end:
            raise ValueError("No JSON object found in AI response")
        return raw[start: end + 1]

    def _ensure_source_refs(self, case: GeneratedTestCase) -> GeneratedTestCase:
        refs = [ref for ref in case.来源 if ref]
        if refs:
            return case
        return case.model_copy(update={"来源": [f"current:{case.编号}"]})
