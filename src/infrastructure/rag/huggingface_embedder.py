"""Infrastructure RAG Embedder - Mã hóa văn bản sang vector bằng HuggingFace SentenceTransformer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.application.rag_service import EmbedderPort
from src.domain.ports import LoggerPort, NullLogger

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class HuggingFaceEmbedder(EmbedderPort):
    """Adapter mã hóa câu truy vấn bằng mô hình Bi-Encoder (mặc định: bkai-foundation-models/vietnamese-bi-encoder)."""

    def __init__(
        self,
        model_name: str = "bkai-foundation-models/vietnamese-bi-encoder",
        logger: LoggerPort | None = None,
    ):
        self.model_name = model_name
        self.logger: LoggerPort = logger or NullLogger()
        self._model: SentenceTransformer | None = None

    def _get_model(self) -> SentenceTransformer:
        """Lazy-load mô hình chỉ khi thực sự gọi tìm kiếm (giúp ứng dụng khởi động nhanh)."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self.logger.info(f"Đang tải mô hình Embedding '{self.model_name}'...")
            self._model = SentenceTransformer(self.model_name)
            self.logger.info(f"Đã tải xong mô hình Embedding '{self.model_name}'")
        return self._model

    def embed_query(self, text: str) -> list[float]:
        """Chuyển câu truy vấn tiếng Việt thành vector 768 chiều."""
        model = self._get_model()
        vector = model.encode(text, normalize_embeddings=True)
        return vector.tolist()
