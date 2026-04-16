from __future__ import annotations

import json
import time

from config import get_settings
from models.schemas import AnalysisArtifact, AnalysisPayload
from prompts.analysis_prompt import build_analysis_prompt
from services.ai_client import get_ai_client


class AnalysisService:
    def __init__(self) -> None:
        get_settings()  # 触发配置校验

    def analyze(self, document_id: str, text: str) -> AnalysisArtifact:
        payload = self._call_with_retries(text)
        validated = AnalysisPayload.model_validate(payload)
        return AnalysisArtifact(
            document_id=document_id,
            summary=validated.summary,
            features=validated.features,
            business_rules=validated.business_rules,
            boundary_conditions=validated.boundary_conditions,
            open_questions=validated.open_questions,
        )

    def _call_with_retries(self, text: str) -> dict:
        prompt = build_analysis_prompt(text)
        last_error: Exception | None = None
        settings = get_settings()
        for attempt in range(1, settings.max_retries + 1):
            try:
                client = get_ai_client()
                raw = client.generate(prompt, max_tokens=4000)
                parsed = self._parse_response(raw)
                AnalysisPayload.model_validate(parsed)
                return parsed
            except Exception as exc:
                last_error = exc
                if attempt == settings.max_retries:
                    break
                time.sleep(2 ** (attempt - 1))
        raise RuntimeError("AI analysis failed after retries") from last_error

    def _parse_response(self, raw: str) -> dict:
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return json.loads(self._extract_json_object(raw))

    def _extract_json_object(self, raw: str) -> str:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or start >= end:
            raise ValueError("No JSON object found in AI response")
        return raw[start: end + 1]
