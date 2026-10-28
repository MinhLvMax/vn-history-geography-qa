"""Mô hình dữ liệu và thông điệp ngữ cảnh hội thoại."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from src.domain.ports import Tool


# --- Multimodal Content Parts ---

@dataclass
class TextPart:
    """Nội dung dạng văn bản thuần."""
    text: str


@dataclass
class ImagePart:
    """Nội dung dạng hình ảnh (bytes và mime_type)."""
    data: bytes
    mime_type: str  # Ví dụ: 'image/png', 'image/jpeg'...


@dataclass
class VideoPart:
    """Nội dung dạng video (bytes và mime_type)."""
    data: bytes
    mime_type: str  # Ví dụ: 'video/mp4'...


ContentPart = Union[TextPart, ImagePart, VideoPart]


def parts_to_text(parts: list[ContentPart]) -> str:
    """Chuyển đổi danh sách ContentPart thành chuỗi văn bản (ảnh/video được thay bằng nhãn mô tả)."""
    texts: list[str] = []
    for part in parts:
        if isinstance(part, TextPart):
            texts.append(part.text)
        elif isinstance(part, (ImagePart, VideoPart)):
            texts.append(f"[{type(part).__name__}: {part.mime_type}]")
        else:
            texts.append(str(part))
    return "\n".join(texts)


# --- Messages ---

@dataclass
class SystemMessage:
    """Chỉ thị hệ thống thiết lập vai trò và ngữ cảnh hoạt động của Agent."""
    content: str


@dataclass
class UserMessage:
    """Thông điệp từ phía người dùng gửi tới Agent."""
    content: list[ContentPart]


@dataclass
class AssistantMessage:
    """Phản hồi dạng văn bản/nội dung từ Agent."""
    content: list[ContentPart]


@dataclass
class ToolCallMessage:
    """Yêu cầu gọi tool do LLM sinh ra."""

    @dataclass
    class ToolCall:
        """Chi tiết một lệnh gọi tool."""
        id: str
        name: str
        kwargs: dict

    tool_calls: list[ToolCall]


@dataclass
class ToolResultMessage:
    """Kết quả trả về sau khi thực thi một lệnh gọi tool."""
    tool_call_id: str
    name: str
    content: list[ContentPart]
    is_error: bool = False  # True khi tool chạy lỗi (nội dung là thông báo lỗi gửi lại cho LLM)


Message = Union[SystemMessage, UserMessage, AssistantMessage, ToolCallMessage, ToolResultMessage]
Decision = Union[AssistantMessage, ToolCallMessage]


# --- Context & Execution Result ---

@dataclass
class AgentContext:
    """Ngữ cảnh của Agent trong phiên làm việc."""
    system_prompt: str
    history: list[Message]
    tools: list[Tool]

    def add_message(self, message: Message) -> None:
        """Thêm một message vào lịch sử trò chuyện."""
        self.history.append(message)

    def get_messages(self) -> list[Message]:
        """Lấy toàn bộ messages bao gồm system prompt và lịch sử trò chuyện."""
        return [SystemMessage(content=self.system_prompt)] + self.history


@dataclass
class AgentThinkingResult:
    """Kết quả đầu ra sau chu trình suy luận của Agent."""
    messages: list[Message]
