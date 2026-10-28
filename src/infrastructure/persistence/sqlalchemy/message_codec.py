"""Chuyển đổi giữa domain Message và bản ghi CSDL."""

import base64
from typing import Any

from src.domain.exceptions import MessageTypeDoesNotExist
from src.domain.models import (
    AssistantMessage,
    ContentPart,
    ImagePart,
    Message,
    TextPart,
    ToolCallMessage,
    ToolResultMessage,
    UserMessage,
    VideoPart,
)


def _encode_part(part: ContentPart) -> dict[str, Any]:
    if isinstance(part, TextPart):
        return {"type": "text", "text": part.text}
    if isinstance(part, (ImagePart, VideoPart)):
        return {
            "type": "image" if isinstance(part, ImagePart) else "video",
            "mime_type": part.mime_type,
            "data_b64": base64.b64encode(part.data).decode("ascii"),
        }
    raise MessageTypeDoesNotExist(f"ContentPart {type(part).__name__} không hỗ trợ lưu trữ")


def _decode_part(data: dict[str, Any]) -> ContentPart:
    if data["type"] == "text":
        return TextPart(text=data["text"])
    part_cls = ImagePart if data["type"] == "image" else VideoPart
    return part_cls(data=base64.b64decode(data["data_b64"]), mime_type=data["mime_type"])


def encode_message(message: Message) -> tuple[str, dict[str, Any]]:
    """Chuyển domain Message thành (kind, payload) để lưu."""
    if isinstance(message, UserMessage):
        return "user", {"content": [_encode_part(p) for p in message.content]}
    if isinstance(message, AssistantMessage):
        return "assistant", {"content": [_encode_part(p) for p in message.content]}
    if isinstance(message, ToolCallMessage):
        return "tool_call", {
            "tool_calls": [
                {"id": tc.id, "name": tc.name, "kwargs": tc.kwargs} for tc in message.tool_calls
            ]
        }
    if isinstance(message, ToolResultMessage):
        return "tool_result", {
            "tool_call_id": message.tool_call_id,
            "name": message.name,
            "content": [_encode_part(p) for p in message.content],
            "is_error": message.is_error,
        }
    raise MessageTypeDoesNotExist(f"Message {type(message).__name__} không hỗ trợ lưu trữ")


def decode_message(kind: str, payload: dict[str, Any]) -> Message:
    """Dựng lại domain Message từ (kind, payload) đã lưu."""
    if kind == "user":
        return UserMessage(content=[_decode_part(p) for p in payload["content"]])
    if kind == "assistant":
        return AssistantMessage(content=[_decode_part(p) for p in payload["content"]])
    if kind == "tool_call":
        return ToolCallMessage(
            tool_calls=[
                ToolCallMessage.ToolCall(id=tc["id"], name=tc["name"], kwargs=tc["kwargs"])
                for tc in payload["tool_calls"]
            ]
        )
    if kind == "tool_result":
        return ToolResultMessage(
            tool_call_id=payload["tool_call_id"],
            name=payload["name"],
            content=[_decode_part(p) for p in payload["content"]],
            is_error=payload.get("is_error", False),
        )
    raise MessageTypeDoesNotExist(f"Loại message '{kind}' không hợp lệ")
