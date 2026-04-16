from __future__ import annotations

import html
import logging
import traceback
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Header, UploadFile
from sqlalchemy.exc import IntegrityError

from config import get_settings
from models.schemas import AnalysisPayload, ErrorResponse, GenerationResponse, UploadResponse
from services.analysis_service import AnalysisService
from services.document_ingestion import DocumentIngestionService, ExtractionError, UnsupportedFileError
from services.embedding_service import get_embedding_service
from services.retrieval_service import RetrievalService
from services.test_generation import TestGenerationService
from storage.chroma_client import get_vector_store
from storage.sqlite_store import get_sqlite_store

router = APIRouter()

# ── 认证依赖 ────────────────────────────────────────────────────────────────
async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")) -> str:
    settings = get_settings()
    if not settings.api_key:
        # 未配置 API Key 时跳过认证（开发模式）
        return "dev"
    if x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key


# ── HTML 转义工具 ───────────────────────────────────────────────────────────
def escape_html(text: str) -> str:
    """转义 HTML 特殊字符，防止 XSS 注入"""
    return html.escape(text, quote=True)


# ── 日志配置 ────────────────────────────────────────────────────────────────
LOG_FILE = Path("data/app.log")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

_logger = logging.getLogger("api")
_logger.setLevel(logging.DEBUG)
_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
if not _logger.handlers:
    _logger.addHandler(_handler)


def _log(doc_id: str, step: str, msg: str, exc: Exception | None = None):
    ts = datetime.now().strftime("%H:%M:%S")
    prefix = f"[{ts}] [{step}]"
    if exc:
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        _logger.error(f"{prefix} {msg}\n  exc: {exc}\n{tb}")
    else:
        _logger.info(f"{prefix} {msg}")


def _build_services() -> tuple[DocumentIngestionService, AnalysisService, RetrievalService, TestGenerationService]:
    vector_store = get_vector_store()
    embedding_service = get_embedding_service()
    retrieval = RetrievalService(vector_store=vector_store, embedding_service=embedding_service)
    return (
        DocumentIngestionService(),
        AnalysisService(),
        retrieval,
        TestGenerationService(),
    )


@router.post(
    "/documents/upload",
    response_model=UploadResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def upload_document(file: UploadFile = File(...), _auth: str = Depends(verify_api_key)) -> UploadResponse:
    ingestion_service, analysis_service, retrieval_service, _ = _build_services()
    store = get_sqlite_store()

    try:
        ingested = await ingestion_service.ingest(file)
    except UnsupportedFileError as exc:
        raise HTTPException(status_code=400, detail="Unsupported file type") from exc
    except ExtractionError as exc:
        raise HTTPException(status_code=400, detail="Failed to extract document content") from exc

    existing = store.get_document_by_checksum(ingested.checksum)
    if existing is not None:
        return UploadResponse(
            document_id=existing.id,
            filename=existing.filename,
            status=existing.status,
            duplicate=True,
            message="Duplicate upload detected; existing document reused",
        )

    try:
        document = store.create_document(
            document_id=ingested.document_id,
            filename=ingested.filename,
            file_type=ingested.file_type,
            checksum=ingested.checksum,
            content_text=ingested.text,
        )
    except Exception as exc:
        existing = store.get_document_by_checksum(ingested.checksum)
        if existing is not None:
            return UploadResponse(
                document_id=existing.id,
                filename=existing.filename,
                status=existing.status,
                duplicate=True,
                message="Duplicate upload detected; existing document reused",
            )
        raise HTTPException(status_code=500, detail="Document creation failed") from exc

    try:
        artifact = analysis_service.analyze(document.id, ingested.text)
        store.save_analysis(artifact)
        chunks = ingestion_service.chunk_text(ingested.text)
        retrieval_service.store_document_chunks(document.id, document.filename, chunks)
        retrieval_service.store_analysis_artifact(artifact, document.filename)
        store.mark_document_status(document.id, "analyzed")
        return UploadResponse(
            document_id=document.id,
            filename=document.filename,
            status="analyzed",
            duplicate=False,
            message="Document analyzed and stored successfully",
        )
    except Exception as exc:
        # 分析失败，但文档已存——标记状态让用户可单独重试
        store.mark_document_status(document.id, "analysis_failed", extraction_error="Internal analysis error")
        return UploadResponse(
            document_id=document.id,
            filename=document.filename,
            status="analysis_failed",
            duplicate=False,
            message="Analysis failed. Use the retry button to try again.",
        )


@router.post(
    "/documents/{document_id}/generate",
    response_model=GenerationResponse,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def generate_test_cases(document_id: str, _auth: str = Depends(verify_api_key)) -> GenerationResponse:
    _, _, retrieval_service, generation_service = _build_services()
    store = get_sqlite_store()

    document = store.get_document(document_id)

    artifact = store.get_analysis(document_id)

    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    if artifact is None:
        raise HTTPException(status_code=404, detail="Analysis artifact not found")

    try:
        retrieved_context = retrieval_service.retrieve_similar_context(artifact)

        _log(document_id, "GENERATE", "开始调用 AI 生成测试用例")
        response = generation_service.generate(artifact, retrieved_context)

        store.replace_test_cases(document_id, response.test_cases)
        store.mark_document_status(document_id, "generated")
        return response
    except Exception as exc:
        try:
            _log(document_id, "ERROR", "生成失败", exc)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="Test generation failed. Please try again.") from exc


@router.get(
    "/documents/{document_id}/test-cases",
    response_model=GenerationResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_test_cases(document_id: str, _auth: str = Depends(verify_api_key)) -> GenerationResponse:
    store = get_sqlite_store()
    document = store.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    artifact = store.get_analysis(document_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Analysis artifact not found")

    test_cases = store.get_test_cases(document_id)
    return GenerationResponse(
        document_id=document_id,
        test_cases=test_cases,
        retrieved_context_count=0,
    )


@router.get(
    "/documents/{document_id}/analysis",
    response_model=AnalysisPayload,
    responses={404: {"model": ErrorResponse}},
)
async def get_analysis(document_id: str, _auth: str = Depends(verify_api_key)) -> AnalysisPayload:
    store = get_sqlite_store()
    artifact = store.get_analysis(document_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Analysis artifact not found")

    return AnalysisPayload(
        summary=artifact.summary,
        features=artifact.features,
        business_rules=artifact.business_rules,
        boundary_conditions=artifact.boundary_conditions,
        open_questions=artifact.open_questions,
    )


@router.post(
    "/documents/{document_id}/analyze",
    response_model=AnalysisPayload,
    responses={404: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def retry_analyze(document_id: str, _auth: str = Depends(verify_api_key)) -> AnalysisPayload:
    """Retry analysis for a document that previously failed."""
    store = get_sqlite_store()
    document = store.get_document(document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.status == "analyzed":
        artifact = store.get_analysis(document_id)
        if artifact is not None:
            return AnalysisPayload(
                summary=artifact.summary,
                features=artifact.features,
                business_rules=artifact.business_rules,
                boundary_conditions=artifact.boundary_conditions,
                open_questions=artifact.open_questions,
            )

    _, analysis_service, retrieval_service, _ = _build_services()
    ingestion_svc = DocumentIngestionService()

    try:
        artifact = analysis_service.analyze(document.id, document.content_text)
        store.save_analysis(artifact)
        chunks = ingestion_svc.chunk_text(document.content_text)
        retrieval_service.store_document_chunks(document.id, document.filename, chunks)
        retrieval_service.store_analysis_artifact(artifact, document.filename)
        store.mark_document_status(document.id, "analyzed")
        return AnalysisPayload(
            summary=artifact.summary,
            features=artifact.features,
            business_rules=artifact.business_rules,
            boundary_conditions=artifact.boundary_conditions,
            open_questions=artifact.open_questions,
        )
    except Exception as exc:
        store.mark_document_status(document_id, "analysis_failed", extraction_error="Internal analysis error")
        raise HTTPException(status_code=500, detail="Analysis retry failed. Please try again.") from exc


@router.get(
    "/knowledge-base/stats",
    responses={500: {"model": ErrorResponse}},
)
async def knowledge_base_stats(_auth: str = Depends(verify_api_key)) -> dict:
    store = get_sqlite_store()
    vector_store = get_vector_store()
    stats = store.get_stats(
        chunk_count=vector_store.count_chunks(),
        analysis_count=vector_store.count_analysis(),
    )
    return stats.model_dump()
