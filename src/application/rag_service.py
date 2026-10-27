"""Application RAG Service - Các cổng (Ports) và dịch vụ điều phối luồng truy xuất 2 tầng (Two-Stage RAG).

Luồng chuẩn:
1. EmbedderPort: Chuyển câu truy vấn thành vector (Bi-Encoder).
2. VectorRetrieverPort: Truy xuất nhanh Top-K đoạn văn bản ứng viên từ Vector DB (Qdrant) hoặc lấy theo chunk_ids.
3. RerankerPort: Chấm điểm sâu cặp (query, chunk) bằng Cross-Encoder (PhoRanker) và lọc lấy Top-N.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from src.domain.ports import LoggerPort, NullLogger


@dataclass
class RetrievedChunk:
    """Một đoạn văn bản (chunk) được truy xuất từ kho tri thức."""

    chunk_id: str
    text: str
    vector_score: float = 0.0
    rerank_score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def final_score(self) -> float:
        """Điểm xếp hạng cuối cùng (ưu tiên điểm rerank nếu có)."""
        return self.rerank_score if self.rerank_score is not None else self.vector_score


@runtime_checkable
class EmbedderPort(Protocol):
    """Cổng mã hóa văn bản truy vấn sang vector nhiều chiều (Bi-Encoder)."""

    def embed_query(self, text: str) -> list[float]:
        """Mã hóa câu truy vấn thành vector số thực."""
        ...


@runtime_checkable
class VectorRetrieverPort(Protocol):
    """Cổng truy xuất các đoạn văn bản từ cơ sở dữ liệu Vector (Qdrant)."""

    def retrieve(
        self,
        query_vector: list[float],
        top_k: int = 20,
        collection_name: str | None = None,
    ) -> list[RetrievedChunk]:
        """Tìm kiếm Top-K đoạn văn bản gần nhất với vector truy vấn."""
        ...

    def get_by_chunk_ids(
        self,
        chunk_ids: list[str],
        collection_name: str | None = None,
    ) -> list[RetrievedChunk]:
        """Lấy trực tiếp các đoạn văn bản theo danh sách mã chunk_id (ví dụ: đọc các trang liền kề)."""
        ...


@runtime_checkable
class RerankerPort(Protocol):
    """Cổng xếp hạng lại (Cross-Encoder Reranker) các đoạn văn bản ứng viên."""

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_n: int = 5,
    ) -> list[RetrievedChunk]:
        """Chấm điểm lại các đoạn văn bản dựa trên sự tương tác trực tiếp với câu hỏi và trả về Top-N."""
        ...


class RagSearchService:
    """Application Service điều phối pipeline RAG 2 tầng (Retrieve -> Rerank) và tra cứu theo chunk_id."""

    def __init__(
        self,
        embedder: EmbedderPort,
        retriever: VectorRetrieverPort,
        reranker: RerankerPort | None = None,
        logger: LoggerPort | None = None,
        default_retrieve_top_k: int = 20,
        default_rerank_top_n: int = 5,
    ):
        self.embedder = embedder
        self.retriever = retriever
        self.reranker = reranker
        self.logger: LoggerPort = logger or NullLogger()
        self.default_retrieve_top_k = default_retrieve_top_k
        self.default_rerank_top_n = default_rerank_top_n

    def search(
        self,
        query: str,
        retrieve_top_k: int | None = None,
        rerank_top_n: int | None = None,
        collection_name: str | None = None,
    ) -> list[RetrievedChunk]:
        """Thực thi toàn bộ pipeline: Bi-Encoder Embed -> Qdrant Retrieve -> Cross-Encoder Rerank."""
        cleaned_query = query.strip()
        if not cleaned_query:
            return []

        top_k = retrieve_top_k or self.default_retrieve_top_k
        top_n = rerank_top_n or self.default_rerank_top_n
        # Đảm bảo số ứng viên lấy từ Qdrant luôn >= số lượng kết quả cần lấy sau rerank
        if top_k < top_n:
            top_k = top_n

        self.logger.info(
            f"[RAG] Bắt đầu tìm kiếm cho truy vấn: '{cleaned_query}' (top_k={top_k}, top_n={top_n})"
        )

        # Bước 1: Mã hóa câu truy vấn thành vector
        query_vector = self.embedder.embed_query(cleaned_query)

        # Bước 2: Truy xuất rộng Top-K ứng viên từ Vector DB
        candidates = self.retriever.retrieve(
            query_vector=query_vector,
            top_k=top_k,
            collection_name=collection_name,
        )
        self.logger.info(f"[RAG] Đã lấy {len(candidates)} ứng viên từ Vector DB")

        if not candidates:
            return []

        # Bước 3: Xếp hạng lại bằng Cross-Encoder (nếu được cấu hình)
        if self.reranker is not None:
            ranked_chunks = self.reranker.rerank(
                query=cleaned_query,
                chunks=candidates,
                top_n=top_n,
            )
            self.logger.info(
                f"[RAG] Đã rerank và chọn ra {len(ranked_chunks)} đoạn văn phù hợp nhất"
            )
            return ranked_chunks

        return candidates[:top_n]

    def get_by_chunk_ids(
        self,
        chunk_ids: list[str],
        collection_name: str | None = None,
    ) -> list[RetrievedChunk]:
        """Lấy trực tiếp các đoạn tư liệu theo danh sách mã chunk_id."""
        cleaned_ids = [cid.strip() for cid in chunk_ids if cid and cid.strip()]
        if not cleaned_ids:
            return []

        self.logger.info(f"[RAG] Đang lấy trực tiếp {len(cleaned_ids)} chunk theo ID: {cleaned_ids}")
        chunks = self.retriever.get_by_chunk_ids(
            chunk_ids=cleaned_ids,
            collection_name=collection_name,
        )
        self.logger.info(f"[RAG] Đã tìm thấy {len(chunks)}/{len(cleaned_ids)} chunk theo ID")
        return chunks
