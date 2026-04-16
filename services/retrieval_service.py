from __future__ import annotations

from collections import OrderedDict

from config import get_settings
from models.schemas import AnalysisArtifact, RetrievedContextItem
from services.embedding_service import EmbeddingService
from storage.chroma_client import flatten_query_results


class RetrievalService:
    def __init__(self, vector_store, embedding_service: EmbeddingService) -> None:
        self.vector_store = vector_store
        self.embedding_service = embedding_service
        self.settings = get_settings()

    def store_document_chunks(self, document_id: str, filename: str, chunks: list[str]) -> None:
        if not chunks:
            return
        ids = [f"{document_id}:chunk:{i}" for i in range(len(chunks))]
        embeddings = self.embedding_service.embed(chunks)
        metadatas = [
            {"document_id": document_id, "filename": filename, "source_type": "raw_chunk", "chunk_index": i}
            for i in range(len(chunks))
        ]
        self.vector_store.upsert_requirement_chunks(ids, chunks, embeddings, metadatas)

    def store_analysis_artifact(self, artifact: AnalysisArtifact, filename: str) -> None:
        documents: list[str] = []
        ids: list[str] = []
        metadatas: list[dict] = []

        if artifact.summary:
            ids.append(f"{artifact.document_id}:analysis:summary")
            documents.append(artifact.summary)
            metadatas.append(self._metadata(artifact.document_id, filename, "summary", 0))

        for label, values in (
            ("feature", artifact.features),
            ("business_rule", artifact.business_rules),
            ("boundary_condition", artifact.boundary_conditions),
        ):
            for i, value in enumerate(values):
                ids.append(f"{artifact.document_id}:analysis:{label}:{i}")
                documents.append(value)
                metadatas.append(self._metadata(artifact.document_id, filename, label, i))

        if not documents:
            return
        embeddings = self.embedding_service.embed(documents)
        self.vector_store.upsert_requirement_analysis(ids, documents, embeddings, metadatas)

    def retrieve_similar_context(
        self,
        artifact: AnalysisArtifact,
        limit: int = 8,
    ) -> list[RetrievedContextItem]:
        query_texts = [artifact.summary, *artifact.features[:4], *artifact.business_rules[:4]]
        query_texts = [item for item in query_texts if item]
        if not query_texts:
            return []

        query_embeddings = self.embedding_service.embed(query_texts)
        results = self.vector_store.query_requirement_analysis(query_embeddings, limit=limit)

        deduped: OrderedDict[str, RetrievedContextItem] = OrderedDict()
        for row in flatten_query_results(results):
            metadata = row["metadata"]
            if metadata.get("document_id") == artifact.document_id:
                continue
            score = min(1.0, max(0.0, 1.0 - row["distance"]))
            if score < self.settings.retrieval_score_threshold:
                continue
            key = f"{metadata.get('document_id')}::{row['document']}"
            if key in deduped and deduped[key].score >= score:
                continue
            deduped[key] = RetrievedContextItem(
                document_id=str(metadata.get("document_id")),
                score=score,
                content_type=self._map_content_type(str(metadata.get("source_type", "summary"))),
                content=row["document"],
                metadata={str(k): v for k, v in metadata.items()},
            )
            if len(deduped) >= limit:
                break
        return list(deduped.values())

    def _metadata(self, document_id: str, filename: str, source_type: str, index: int) -> dict:
        return {
            "document_id": document_id,
            "filename": filename,
            "source_type": source_type,
            "item_index": index,
        }

    def _map_content_type(self, value: str) -> str:
        mapping = {
            "summary": "summary",
            "feature": "feature",
            "business_rule": "business_rule",
            "boundary_condition": "boundary_condition",
        }
        return mapping.get(value, "summary")
