"""Infrastructure LLM - Adapter kết nối với Ollama (chạy local hoặc Ollama Cloud/Server).

Sử dụng trực tiếp REST API `/api/chat` của Ollama qua `httpx` để hỗ trợ đầy đủ:
- Function / Tool calling chuẩn của Ollama (`tools`, `tool_calls`, `role="tool"`).
- Chế độ suy luận (`think`: `True`/`False` hoặc mức độ `"low"`, `"medium"`, `"high"`).
- Tùy chọn xác thực Bearer token (`api_key`) khi kết nối tới Ollama Cloud hoặc reverse proxy.
"""

import json
import uuid
from typing import Any

import httpx

from src.domain.exceptions import AppError, MessageTypeDoesNotExist
from src.domain.models import (
    AgentContext,
    AssistantMessage,
    Decision,
    Message,
    SystemMessage,
    TextPart,
    ToolCallMessage,
    ToolResultMessage,
    UserMessage,
    parts_to_text,
)
from src.domain.ports import LLMPort, Tool

DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"


class OllamaError(AppError):
    """Lỗi xảy ra khi kết nối hoặc gọi API của Ollama thất bại."""
    pass


def _parse_think_value(think: str | bool | None) -> bool | str | None:
    """Chuyển chuỗi chế độ suy luận từ cấu hình model sang giá trị `think` của Ollama API.

    - None / "" -> None (theo mặc định của model)
    - "true", "on", "yes", "1", "enabled", "think" -> True
    - "false", "off", "no", "0", "disabled", "none" -> False
    - Các mức khác (vd. "low", "medium", "high") -> giữ nguyên chuỗi.
    """
    if think is None or isinstance(think, bool):
        return think
    normalized = think.strip().lower()
    if not normalized:
        return None
    if normalized in {"true", "on", "yes", "1", "enabled", "think"}:
        return True
    if normalized in {"false", "off", "no", "0", "disabled", "none"}:
        return False
    return think.strip()


class OllamaLLM(LLMPort):
    """Adapter triển khai LLMPort sử dụng Ollama `/api/chat`."""

    def __init__(
        self,
        model_name: str,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        api_key: str | None = None,
        reasoning_effort: str | bool | None = None,
        builtin_tools: list[str] | None = None,
        timeout: float = 300.0,
    ):
        self.model_name = model_name
        self.base_url = (base_url or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
        # Cho phép truyền sẵn URL có hậu tố /api hoặc /v1 mà vẫn chuẩn hóa về gốc
        for suffix in ("/api/chat", "/api", "/v1"):
            if self.base_url.endswith(suffix):
                self.base_url = self.base_url[: -len(suffix)].rstrip("/")
                break
        self.api_key = api_key
        self.reasoning_effort = reasoning_effort
        self.builtin_tools = builtin_tools or []
        self.timeout = timeout

    def decide(self, context: AgentContext) -> Decision:
        """Gửi ngữ cảnh hội thoại và danh sách tool tới Ollama để nhận câu trả lời hoặc tool call."""
        messages = [self._to_ollama_message(message) for message in context.get_messages()]
        tools = [self._to_ollama_tool(tool) for tool in context.tools]
        tools += [{"type": name} for name in self.builtin_tools]

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        think_value = _parse_think_value(self.reasoning_effort)
        if think_value is not None:
            payload["think"] = think_value

        data = self._post_chat(payload)
        response_message = data.get("message") or {}

        tool_calls = response_message.get("tool_calls") or []
        if tool_calls:
            return ToolCallMessage(
                tool_calls=[self._from_ollama_tool_call(tc) for tc in tool_calls]
            )

        content = (response_message.get("content") or "").strip()
        return AssistantMessage(
            content=[TextPart(content or "Không có câu trả lời")]
        )

    def _post_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Gửi HTTP POST tới `/api/chat` của Ollama và xử lý lỗi."""
        url = f"{self.base_url}/api/chat"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise OllamaError(f"Ollama quá thời gian chờ ({self.timeout:.0f}s) tại {url}") from exc
        except httpx.RequestError as exc:
            raise OllamaError(
                f"Không kết nối được tới Ollama tại {self.base_url}. "
                f"Hãy kiểm tra dịch vụ Ollama đã chạy chưa ({exc})."
            ) from exc

        if response.status_code >= 400:
            detail = response.text.strip()
            try:
                err_json = response.json()
                if isinstance(err_json, dict) and err_json.get("error"):
                    detail = str(err_json["error"])
            except ValueError:
                pass
            raise OllamaError(f"Ollama trả về lỗi (HTTP {response.status_code}): {detail}")

        try:
            data = response.json()
        except ValueError as exc:
            raise OllamaError(
                f"Không parse được JSON phản hồi từ Ollama: {response.text[:500]}"
            ) from exc

        if isinstance(data, dict) and data.get("error"):
            raise OllamaError(f"Ollama trả về lỗi: {data['error']}")

        return data

    def _to_ollama_tool(self, tool: Tool) -> dict[str, Any]:
        """Chuyển đổi Tool domain thành schema function của Ollama."""
        return {
            "type": "function",
            "function": {
                "name": tool.tool_name,
                "description": tool.tool_description,
                "parameters": tool.tool_kwargs.model_json_schema(),
            },
        }

    def _to_ollama_message(self, message: Message) -> dict[str, Any]:
        """Chuyển đổi Message domain thành định dạng message của Ollama `/api/chat`."""
        if isinstance(message, SystemMessage):
            return {
                "role": "system",
                "content": message.content,
            }
        if isinstance(message, UserMessage):
            return {
                "role": "user",
                "content": parts_to_text(message.content),
            }
        if isinstance(message, AssistantMessage):
            return {
                "role": "assistant",
                "content": parts_to_text(message.content),
            }
        if isinstance(message, ToolResultMessage):
            return {
                "role": "tool",
                "tool_name": message.name,
                "content": parts_to_text(message.content),
            }
        if isinstance(message, ToolCallMessage):
            return {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": tool_call.name,
                            "arguments": (
                                tool_call.kwargs
                                if isinstance(tool_call.kwargs, dict)
                                else json.loads(str(tool_call.kwargs) or "{}")
                            ),
                        },
                    }
                    for tool_call in message.tool_calls
                ],
            }

        raise MessageTypeDoesNotExist(
            f"Đối tượng {type(message).__name__} không phù hợp khi convert sang message của Ollama"
        )

    def _from_ollama_tool_call(self, tc: dict[str, Any]) -> ToolCallMessage.ToolCall:
        """Chuyển đổi một phần tử tool_call từ Ollama sang domain ToolCall."""
        fn = tc.get("function") or {}
        raw_args = fn.get("arguments") or {}
        if isinstance(raw_args, str):
            try:
                kwargs = json.loads(raw_args or "{}")
            except json.JSONDecodeError:
                kwargs = {}
        elif isinstance(raw_args, dict):
            kwargs = raw_args
        else:
            kwargs = {}

        call_id = tc.get("id") or f"call_{uuid.uuid4().hex[:12]}"
        return ToolCallMessage.ToolCall(
            id=call_id,
            name=fn.get("name", ""),
            kwargs=kwargs,
        )
