from collections.abc import Iterable

import chromadb
from chromadb.api.models.Collection import Collection

from config import get_settings


class ChromaVectorStore:
    def __init__(self) -> None:
        settings = get_settings()
        settings.ensure_data_dirs()
        self._client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
        self.requirement_chunks = self._get_or_create_collection("requirement_chunks")
        self.requirement_analysis = self._get_or_create_collection("requirement_analysis")

    def _get_or_create_collection(self, name: str) -> Collection:
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_requirement_chunks(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        self.requirement_chunks.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def upsert_requirement_analysis(
        self,
        ids: list[str],
        documents: list[str],
        embeddings: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        self.requirement_analysis.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )

    def query_requirement_analysis(
        self,
        query_embeddings: list[list[float]],
        limit: int = 5,
    ) -> dict:
        if not query_embeddings:
            return self._empty_query_result(0)

        count = self.requirement_analysis.count()
        if count == 0:
            return self._empty_query_result(len(query_embeddings))

        safe_limit = min(limit, count)
        return self.requirement_analysis.query(
            query_embeddings=query_embeddings,
            n_results=safe_limit,
            include=["documents", "metadatas", "distances"],
        )

    def _empty_query_result(self, rows: int) -> dict:
        return {
            "ids": [[] for _ in range(rows)],
            "documents": [[] for _ in range(rows)],
            "metadatas": [[] for _ in range(rows)],
            "distances": [[] for _ in range(rows)],
            "embeddings": None,
        }

    def count_chunks(self) -> int:
        return self.requirement_chunks.count()

    def count_analysis(self) -> int:
        return self.requirement_analysis.count()

    def delete_document(self, document_id: str) -> None:
        where = {"document_id": document_id}
        self.requirement_chunks.delete(where=where)
        self.requirement_analysis.delete(where=where)


def flatten_query_results(results: dict) -> Iterable[dict]:
    ids = results.get("ids", [[]])
    documents = results.get("documents", [[]])
    metadatas = results.get("metadatas", [[]])
    distances = results.get("distances", [[]])

    for row_ids, row_docs, row_meta, row_dist in zip(ids, documents, metadatas, distances):
        for item_id, item_doc, item_metadata, item_distance in zip(row_ids, row_docs, row_meta, row_dist):
            yield {
                "id": item_id,
                "document": item_doc,
                "metadata": item_metadata or {},
                "distance": float(item_distance),
            }


_vector_store: ChromaVectorStore | None = None


def get_vector_store() -> ChromaVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = ChromaVectorStore()
    return _vector_store
