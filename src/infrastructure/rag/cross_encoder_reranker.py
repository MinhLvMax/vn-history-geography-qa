"""Infrastructure RAG Cross-Encoder Reranker - Chấm điểm và xếp hạng lại kết quả bằng PhoRanker / CrossEncoder.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.rag_service import RerankerPort, RetrievedChunk
from src.domain.ports import LoggerPort, NullLogger

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder


class CrossEncoderReranker(RerankerPort):
    """Adapter xếp hạng lại (Rerank) các đoạn văn bản bằng mô hình Cross-Encoder (mặc định: itdainb/PhoRanker)."""

    def __init__(
        self,
        model_name: str = "itdainb/PhoRanker",
        max_length: int = 256,
        logger: LoggerPort | None = None,
    ):
        self.model_name = model_name
        self.max_length = max_length
        self.logger: LoggerPort = logger or NullLogger()
        self._model: CrossEncoder | None = None

    def _get_model(self) -> CrossEncoder:
        """Lazy-load mô hình Reranker khi cần sử dụng."""
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self.logger.info(f"Đang tải mô hình Reranker '{self.model_name}'...")
            self._model = CrossEncoder(self.model_name, max_length=self.max_length)
            self.logger.info(f"Đã tải xong mô hình Reranker '{self.model_name}'")
        return self._model

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_n: int = 5,
    ) -> list[RetrievedChunk]:
        """Chấm điểm từng cặp (query, chunk.text) và sắp xếp giảm dần theo điểm Cross-Encoder."""
        if not chunks:
            return []

        model = self._get_model()
        pairs = [(query, chunk.text) for chunk in chunks]
        scores = model.predict(pairs)

        reranked: list[RetrievedChunk] = []
        for chunk, score in zip(chunks, scores):
            chunk.rerank_score = float(score)
            reranked.append(chunk)

        reranked.sort(key=lambda item: item.rerank_score or 0.0, reverse=True)
        return reranked[:top_n]
