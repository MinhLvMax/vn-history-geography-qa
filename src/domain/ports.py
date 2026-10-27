"""Domain Ports - Định nghĩa các hợp đồng giao tiếp (Protocols) của tầng Domain.
"""

from typing import Any, Protocol, runtime_checkable
from pydantic import BaseModel

from src.domain.models import AgentContext, ContentPart, Decision


@runtime_checkable
class Tool(Protocol):
    """Quy chuẩn (Protocol) bắt buộc cho một Tool trong hệ thống."""

    class ToolKwargs(BaseModel):
        """Schema tham số đầu vào của tool (được kế thừa từ Pydantic BaseModel)."""
        ...

    class ToolResult(Protocol):
        """Kết quả trả về của tool phải tự biết cách biểu diễn thành các ContentPart."""
        def to_parts(self) -> list[ContentPart]:
            ...

    tool_name: str
    tool_description: str
    tool_kwargs: type[ToolKwargs]

    def execute(self, **kwargs: Any) -> ToolResult:
        """Hàm thực thi logic chính của tool."""
        ...


@runtime_checkable
class LLMPort(Protocol):
    """Cổng giao tiếp chuẩn (Port) với các mô hình ngôn ngữ lớn (LLM)."""

    def decide(self, context: AgentContext) -> Decision:
        """Đưa ra quyết định tiếp theo (trả lời người dùng hoặc gọi tool) dựa trên ngữ cảnh."""
        ...


@runtime_checkable
class LoggerPort(Protocol):
    """Cổng giao tiếp trừu tượng cho dịch vụ logging của hệ thống."""

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        ...

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        ...

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        ...

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        ...


class NullLogger:
    """Null Object triển khai LoggerPort để làm giá trị mặc định khi tắt log hoặc viết unit test."""

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        pass
