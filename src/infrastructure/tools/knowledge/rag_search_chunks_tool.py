"""Công cụ tìm kiếm ngữ nghĩa văn bản qua Vector RAG Pipeline."""

from dataclasses import dataclass
from typing import Any

from pydantic import Field

from src.application.rag_service import RagSearchService, RetrievedChunk
from src.domain.models import ContentPart, TextPart
from src.domain.ports import Tool


class RAGSearchChunksTool(Tool):
    """Công cụ tìm kiếm ngữ nghĩa các đoạn tư liệu Lịch sử & Địa lý Việt Nam (Vector DB + Reranker)."""

    tool_name = "rag_search_chunks"
    tool_description = (
        "Tìm kiếm theo ngữ nghĩa các đoạn văn bản tư liệu gốc về Lịch sử và Địa lý Việt Nam. "
        "Sử dụng công cụ này khi cần tìm nội dung chi tiết, diễn biến sự kiện, bối cảnh lịch sử, "
        "nhân vật, triều đại, trận đánh, niên đại hoặc địa danh. "
        "Nên truyền vào câu hỏi hoặc cụm từ khóa tiếng Việt rõ ràng, tập trung vào một chủ đề cụ thể."
    )

    class ToolKwargs(Tool.ToolKwargs):
        query: str = Field(
            ...,
            description=(
                "Câu hỏi hoặc cụm từ khóa tiếng Việt cần tìm trong kho tư liệu "
                "(ví dụ: 'Chiến thắng Bạch Đằng năm 938 của Ngô Quyền', 'Sự thành lập nhà Trần năm 1225')."
            ),
        )
        top_n: int = Field(
            default=4,
            ge=1,
            le=5,
            description="Số lượng đoạn tư liệu phù hợp nhất muốn lấy sau khi Rerank (mặc định: 4, tối đa: 5).",
        )

    @dataclass
    class Result:
        """Kết quả trả về của công cụ tìm kiếm đoạn tư liệu."""

        query: str
        chunks: list[RetrievedChunk]

        def to_parts(self) -> list[ContentPart]:
            if not self.chunks:
                return [
                    TextPart(
                        f"Không tìm thấy đoạn tư liệu nào phù hợp cho truy vấn: '{self.query}'."
                    )
                ]

            lines: list[str] = [
                f"Tìm thấy {len(self.chunks)} đoạn tư liệu liên quan nhất cho truy vấn '{self.query}':\n"
            ]
            for idx, chunk in enumerate(self.chunks, start=1):
                rerank_info = (
                    f" | Điểm Rerank: {chunk.rerank_score:.4f}"
                    if chunk.rerank_score is not None
                    else ""
                )
                lines.append(
                    f"--- [Tư liệu #{idx} | chunk_id: {chunk.chunk_id} | "
                    f"Điểm Vector: {chunk.vector_score:.4f}{rerank_info}] ---\n"
                    f"{chunk.text}\n"
                )
            return [TextPart("\n".join(lines))]

    tool_kwargs = ToolKwargs

    def __init__(self, rag_service: RagSearchService):
        self.rag_service = rag_service

    def execute(self, **kwargs: Any) -> Result:
        validated = self.ToolKwargs(**kwargs)
        chunks = self.rag_service.search(
            query=validated.query,
            rerank_top_n=validated.top_n,
        )
        return self.Result(query=validated.query, chunks=chunks)
