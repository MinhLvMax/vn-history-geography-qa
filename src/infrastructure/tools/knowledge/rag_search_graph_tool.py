"""Infrastructure Tools - Công cụ truy vấn mạng lưới thực thể và mối quan hệ từ Đồ thị Tri thức (GraphRAG).

Không giả định trước CSDL đồ thị có nhãn (label) hay loại quan hệ (relation_type) cụ thể nào.
"""

from dataclasses import dataclass
import json
from typing import Any

from pydantic import Field

from src.application.rag_service import GraphSearchResult, RagSearchService
from src.domain.models import ContentPart, TextPart
from src.domain.ports import Tool


class RAGSearchGraphTool(Tool):
    """Công cụ truy vấn thực thể và các mối quan hệ liên kết trên Đồ thị Tri thức (Neo4j)."""

    tool_name = "rag_search_graph"
    tool_description = (
        "Tra cứu các thực thể và mạng lưới mối quan hệ giữa chúng trong cơ sở dữ liệu Đồ thị Tri thức "
        "Lịch sử & Địa lý Việt Nam. "
        "Sử dụng công cụ này khi cần: "
        "(1) Khám phá tất cả các sự kiện, nhân vật, tổ chức, địa danh, văn kiện... có liên hệ với một hoặc nhiều thực thể; "
        "(2) Tìm mối liên hệ trực tiếp hoặc bắc cầu (1-2 bước) giữa hai hay nhiều thực thể khác nhau; "
        "(3) Truy vết chuỗi sự kiện, nguyên nhân - hệ quả, sự kế thừa hoặc phân cấp tổ chức/hành chính."
    )

    class ToolKwargs(Tool.ToolKwargs):
        entities: list[str] = Field(
            ...,
            min_length=1,
            max_length=5,
            description=(
                "Danh sách tên các thực thể hoặc từ khóa ngắn gọn cần tra cứu trên đồ thị "
                "(tối đa 5 thực thể, ví dụ: ['Ngô Quyền', 'Kiều Công Tiễn'] hoặc ['Khởi nghĩa Lam Sơn'])."
            ),
        )
        hop_depth: int = Field(
            default=1,
            ge=1,
            le=2,
            description=(
                "Số bước mở rộng quan hệ từ thực thể gốc: "
                "1 (chỉ lấy quan hệ trực tiếp) hoặc 2 (mở rộng qua thực thể trung gian)."
            ),
        )
        limit: int = Field(
            default=15,
            ge=1,
            le=30,
            description="Số lượng mối quan hệ tối đa muốn lấy (mặc định: 15, tối đa: 30).",
        )

    @dataclass
    class Result:
        """Kết quả trả về khi truy vấn Đồ thị Tri thức."""

        entities: list[str]
        subgraph: GraphSearchResult

        def to_parts(self) -> list[ContentPart]:
            if not self.subgraph.matched_nodes and not self.subgraph.relations:
                return [
                    TextPart(
                        f"Không tìm thấy thực thể hoặc mối quan hệ nào trên đồ thị khớp với: {self.entities}."
                    )
                ]

            lines: list[str] = [
                f"Kết quả truy vấn Đồ thị Tri thức cho {self.entities} "
                f"({len(self.subgraph.matched_nodes)} thực thể khớp, {len(self.subgraph.relations)} mối quan hệ):"
            ]

            if self.subgraph.matched_nodes:
                lines.append("\n### Thực thể khớp trên đồ thị:")
                for node in self.subgraph.matched_nodes:
                    label_tag = f"[{', '.join(node.labels)}] " if node.labels else ""
                    desc = f" — {node.description}" if node.description else ""
                    meta = (
                        f" | Thuộc tính: {json.dumps(node.metadata, ensure_ascii=False)}"
                        if node.metadata
                        else ""
                    )
                    lines.append(f"- {label_tag}{node.name}{desc}{meta}")

            if self.subgraph.relations:
                lines.append("\n### Các mối quan hệ liên kết:")
                for idx, rel in enumerate(self.subgraph.relations, start=1):
                    src_label = f"[{', '.join(rel.source.labels)}] " if rel.source.labels else ""
                    dst_label = f"[{', '.join(rel.target.labels)}] " if rel.target.labels else ""
                    chunk_info = f" | chunk_id: {rel.chunk_id}" if rel.chunk_id else ""
                    meta_info = (
                        f" | Ngữ cảnh: {json.dumps(rel.metadata, ensure_ascii=False)}"
                        if rel.metadata
                        else ""
                    )
                    evidence_info = f'\n  Bằng chứng: "{rel.evidence}"' if rel.evidence else ""
                    lines.append(
                        f"{idx}. ({src_label}{rel.source.name}) --[{rel.relation_type}]--> "
                        f"({dst_label}{rel.target.name}){chunk_info}{meta_info}{evidence_info}"
                    )

            return [TextPart("\n".join(lines))]

    tool_kwargs = ToolKwargs

    def __init__(self, rag_service: RagSearchService):
        self.rag_service = rag_service

    def execute(self, **kwargs: Any) -> Result:
        validated = self.ToolKwargs(**kwargs)
        subgraph = self.rag_service.search_graph(
            entities=validated.entities,
            hop_depth=validated.hop_depth,
            limit=validated.limit,
        )
        return self.Result(entities=validated.entities, subgraph=subgraph)
