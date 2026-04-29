from __future__ import annotations

import json
import logging
import time

from config import get_settings
from models.schemas import AnalysisArtifact, GeneratedTestCase, GenerationPayload, GenerationResponse, RetrievedContextItem
from prompts.generation_prompt import build_generation_prompt
from pydantic import ValidationError
from services.ai_client import get_ai_client

_logger = logging.getLogger("test_generation")


class TestGenerationService:
    def __init__(self) -> None:
        get_settings()  # 触发配置校验

    def generate(
        self,
        artifact: AnalysisArtifact,
        retrieved_context: list[RetrievedContextItem],
    ) -> GenerationResponse:
        _logger.info(f"[TestGen] Starting generation for document: {artifact.document_id}")
        _logger.info(f"[TestGen] Retrieved context count: {len(retrieved_context)}")
        if retrieved_context:
            _logger.info(f"[TestGen] Context sources: {[c.document_id for c in retrieved_context[:3]]}...")

        payload = self._call_with_retries(artifact, retrieved_context)
        validated = GenerationPayload.model_validate(payload)
        cases = [self._ensure_source_refs(case) for case in validated.test_cases]

        _logger.info(f"[TestGen] Generation complete, produced {len(cases)} test cases")
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
        _logger.info(f"[TestGen] Prompt built, length: {len(prompt)} chars")
        _logger.debug(f"[TestGen] Prompt preview: {prompt[:300]}...")

        last_error: Exception | None = None
        settings = get_settings()
        for attempt in range(1, settings.max_retries + 1):
            _logger.info(f"[TestGen] AI call attempt {attempt}/{settings.max_retries}")
            try:
                client = get_ai_client()
                raw = client.generate(prompt, max_tokens=16000)
                _logger.info(f"[TestGen] Raw response length: {len(raw)} chars")
                parsed = self._parse_response(raw)
                _logger.info(f"[TestGen] Parsed JSON keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'N/A'}")
                GenerationPayload.model_validate(parsed)
                _logger.info(f"[TestGen] Pydantic validation passed, {len(parsed.get('test_cases', []))} test cases")
                return parsed
            except ValidationError as exc:
                last_error = exc
                _logger.warning(f"[TestGen] Validation error: {exc}")
                if attempt == settings.max_retries:
                    break
                time.sleep(2 ** (attempt - 1))
            except Exception as exc:
                last_error = exc
                _logger.error(f"[TestGen] Error: {type(exc).__name__}: {exc}")
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
            _logger.info(f"[TestGen] Extracted JSON from non-JSON response, length: {len(extracted)}")
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
