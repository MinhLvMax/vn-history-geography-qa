"""Infrastructure Tools - Công cụ đọc trực tiếp các đoạn tư liệu theo mã trang/chunk_id.
"""

from dataclasses import dataclass
from typing import Any

from pydantic import Field

from src.application.rag_service import RagSearchService, RetrievedChunk
from src.domain.models import ContentPart, TextPart
from src.domain.ports import Tool


class ReadChunksByIdsTool(Tool):
    """Công cụ lấy toàn văn nội dung các trang/đoạn tư liệu theo danh sách mã chunk_id."""

    tool_name = "get_vn_history_chunks_by_ids"
    tool_description = (
        "Đọc trực tiếp nội dung của một hoặc nhiều đoạn/trang tư liệu theo mã `chunk_id` "
        "(ví dụ: ['tap_02_trang_0049', 'tap_02_trang_0050']). "
        "Hãy sử dụng công cụ này khi: "
        "(1) Một đoạn tư liệu tìm được ở bước trước bị cắt lửng câu ở đầu hoặc cuối trang và bạn cần đọc trang liền trước/liền sau để hiểu trọn vẹn ý; "
        "(2) Các kết quả tìm kiếm bị nhảy cóc số trang (ví dụ có trang 0048 và trang 0055 nhưng thiếu diễn biến ở các trang 0049, 0050, 0053, 0054 ở giữa)."
    )

    class ToolKwargs(Tool.ToolKwargs):
        chunk_ids: list[str] = Field(
            ...,
            min_length=1,
            max_length=4,
            description=(
                "Danh sách mã `chunk_id` cần đọc (tối đa 4 mã một lần gọi, "
                "ví dụ: ['tap_02_trang_0049', 'tap_02_trang_0050'])."
            ),
        )

    @dataclass
    class Result:
        """Kết quả trả về khi đọc các trang tư liệu theo chunk_id."""

        requested_ids: list[str]
        chunks: list[RetrievedChunk]

        def to_parts(self) -> list[ContentPart]:
            if not self.chunks:
                return [
                    TextPart(
                        f"Không tìm thấy tư liệu nào khớp với danh sách mã: {self.requested_ids}."
                    )
                ]

            found_ids = {c.chunk_id for c in self.chunks}
            missing_ids = [cid for cid in self.requested_ids if cid not in found_ids]

            lines: list[str] = [
                f"Đã tải {len(self.chunks)} đoạn tư liệu theo mã yêu cầu:\n"
            ]
            for idx, chunk in enumerate(self.chunks, start=1):
                lines.append(
                    f"--- [Tư liệu #{idx} | Nguồn: {chunk.chunk_id}] ---\n"
                    f"{chunk.text}\n"
                )
            if missing_ids:
                lines.append(f"(Lưu ý: Không tìm thấy các mã: {missing_ids})")

            return [TextPart("\n".join(lines))]

    tool_kwargs = ToolKwargs

    def __init__(self, rag_service: RagSearchService):
        self.rag_service = rag_service

    def execute(self, **kwargs: Any) -> Result:
        validated = self.ToolKwargs(**kwargs)
        chunks = self.rag_service.get_by_chunk_ids(chunk_ids=validated.chunk_ids)
        return self.Result(requested_ids=validated.chunk_ids, chunks=chunks)
