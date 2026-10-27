"""Infrastructure RAG Qdrant Retriever - Truy xuất vector hoặc lấy chunk theo ID từ Qdrant.
"""

from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import FieldCondition, Filter, MatchAny

from src.application.rag_service import RetrievedChunk, VectorRetrieverPort
from src.domain.ports import LoggerPort, NullLogger


class QdrantVectorRetriever(VectorRetrieverPort):
    """Adapter truy xuất các đoạn văn bản từ Qdrant Vector Database."""

    def __init__(
        self,
        url: str = "http://localhost:6333",
        default_collection: str = "vnhis",
        logger: LoggerPort | None = None,
    ):
        self.url = url
        self.default_collection = default_collection
        self.logger: LoggerPort = logger or NullLogger()
        self._client: QdrantClient | None = None

    def _get_client(self) -> QdrantClient:
        if self._client is None:
            self._client = QdrantClient(url=self.url)
        return self._client

    def retrieve(
        self,
        query_vector: list[float],
        top_k: int = 20,
        collection_name: str | None = None,
    ) -> list[RetrievedChunk]:
        """Truy vấn Qdrant bằng query_points để lấy Top-K đoạn văn bản tương đồng nhất."""
        target_collection = collection_name or self.default_collection
        client = self._get_client()

        response = client.query_points(
            collection_name=target_collection,
            query=query_vector,
            limit=top_k,
            with_payload=True,
            with_vectors=False,
        )

        results: list[RetrievedChunk] = []
        for point in response.points:
            payload: dict[str, Any] = dict(point.payload or {})
            text = str(payload.pop("text", "")).strip()
            chunk_id = str(payload.pop("chunk_id", point.id))
            results.append(
                RetrievedChunk(
                    chunk_id=chunk_id,
                    text=text,
                    vector_score=float(point.score),
                    metadata=payload,
                )
            )
        return results

    def get_by_chunk_ids(
        self,
        chunk_ids: list[str],
        collection_name: str | None = None,
    ) -> list[RetrievedChunk]:
        """Lấy trực tiếp các đoạn văn bản theo danh sách chunk_id và giữ đúng thứ tự yêu cầu."""
        if not chunk_ids:
            return []

        target_collection = collection_name or self.default_collection
        client = self._get_client()

        points, _ = client.scroll(
            collection_name=target_collection,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="chunk_id",
                        match=MatchAny(any=chunk_ids),
                    )
                ]
            ),
            limit=max(len(chunk_ids) * 2, 20),
            with_payload=True,
            with_vectors=False,
        )

        by_id: dict[str, RetrievedChunk] = {}
        for point in points:
            payload: dict[str, Any] = dict(point.payload or {})
            text = str(payload.pop("text", "")).strip()
            chunk_id = str(payload.pop("chunk_id", point.id))
            by_id[chunk_id] = RetrievedChunk(
                chunk_id=chunk_id,
                text=text,
                vector_score=1.0,
                metadata=payload,
            )

        return [by_id[cid] for cid in chunk_ids if cid in by_id]
