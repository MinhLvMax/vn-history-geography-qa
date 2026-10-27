"""Infrastructure LLM - Adapter gọi model qua Antigravity CLI (`agy`), không dùng API key.

Antigravity CLI hỗ trợ ép định dạng phản hồi bằng `--json-schema` ở chế độ non-interactive
(khi truyền prompt qua `stdin` với `--output-format json`). Adapter mô phỏng tool calling
bằng cách yêu cầu LLM trả về một JSON có dạng {"type": "message" | "tool_calls", ...}
và chuyển đổi kết quả đó thành Decision của domain.
"""

import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

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


class AgyCLIError(AppError):
    """Lỗi xảy ra khi gọi Antigravity CLI (`agy`) thất bại hoặc trả về dữ liệu không hợp lệ."""
    pass


# Schema ép Antigravity CLI trả về quyết định ở dạng JSON có cấu trúc
_DECISION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["message", "tool_calls"]},
        "content": {
            "type": "string",
            "description": "Câu trả lời cho người dùng (khi type='message').",
        },
        "tool_calls": {
            "type": "array",
            "description": "Danh sách tool cần gọi (khi type='tool_calls').",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "kwargs": {"type": "object"},
                },
                "required": ["name", "kwargs"],
            },
        },
    },
    "required": ["type"],
}

_PROTOCOL_INSTRUCTIONS = """\
# Giao thức phản hồi
Bạn đang chạy như bộ não của một agent. Mỗi lượt bạn chỉ đưa ra MỘT quyết định duy nhất thông qua công cụ trả kết quả có cấu trúc (structured output theo json-schema) và KHÔNG in văn bản thuần ra ngoài:
- Trả lời người dùng: {"type": "message", "content": "<câu trả lời>"}
- Gọi tool: {"type": "tool_calls", "tool_calls": [{"name": "<tên tool>", "kwargs": {...}}]}
Các tool trong <tools> KHÔNG thể gọi trực tiếp: muốn dùng tool trong <tools>, hãy trả về JSON type="tool_calls" và hệ thống bên ngoài sẽ thực thi giúp bạn. kwargs phải khớp JSON schema của tool.
Kết quả tool sẽ được gửi lại ở lượt sau trong <conversation> với role="tool"."""


class AgyCLILLM(LLMPort):
    """Adapter triển khai LLMPort bằng cách gọi `agy` qua subprocess ở chế độ non-interactive."""

    def __init__(
        self,
        model_name: str,
        effort: str | None = None,
        builtin_tools: list[str] | None = None,
        agy_path: str | None = None,
        timeout: float = 300,
        cwd: Path | None = None,
    ):
        self.model_name = model_name
        self.effort = effort
        # Tool built-in của Antigravity CLI (vd. search_web, read_url_content) được phép gọi trực tiếp
        self.builtin_tools = builtin_tools or []
        self.timeout = timeout
        self.cwd = cwd
        self.agy_path = agy_path or shutil.which("agy")
        if not self.agy_path:
            raise AgyCLIError(
                "Không tìm thấy lệnh 'agy'. Hãy cài Antigravity CLI và đăng nhập (chạy `agy` một lần)."
            )

    def decide(self, context: AgentContext) -> Decision:
        """Gửi toàn bộ ngữ cảnh cho Antigravity CLI và chuyển kết quả JSON thành Decision."""
        system_prompt = f"{context.system_prompt}\n\n{_PROTOCOL_INSTRUCTIONS}"
        if self.builtin_tools:
            system_prompt += (
                f"\nNgoài ra bạn được phép gọi TRỰC TIẾP các tool built-in của CLI: {', '.join(self.builtin_tools)}. "
                "Không gọi các tool built-in khác ngoài danh sách này. "
                "Các tool trong <tools> vẫn phải gọi qua JSON type=\"tool_calls\"."
            )
        else:
            system_prompt += (
                "\nTuyệt đối KHÔNG gọi bất kỳ tool built-in nào của CLI (như đọc/ghi file, chạy lệnh...), "
                "ngoại trừ công cụ trả về kết quả structured output theo json-schema."
            )
        payload = self._run(prompt=self._build_prompt(system_prompt=system_prompt, context=context))
        return self._to_decision(payload)

    def _run(self, prompt: str) -> dict:
        """Chạy Antigravity CLI ở chế độ non-interactive (stdin) và trả về structured output."""
        cmd = [
            self.agy_path,
            "--output-format", "json",
            "--json-schema", json.dumps(_DECISION_SCHEMA),
            "--model", self.model_name,
            "--disable-slash-commands",
        ]
        if self.effort:
            cmd += ["--effort", self.effort]
        try:
            # Khi truyền dữ liệu qua stdin (không cần cờ -p), agy tự chạy ở chế độ print
            # và đọc toàn bộ prompt từ stdin, tránh giới hạn độ dài command line trên Windows.
            completed = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout,
                cwd=self.cwd,
            )
        except subprocess.TimeoutExpired as e:
            raise AgyCLIError(f"Antigravity CLI quá thời gian chờ ({self.timeout}s)") from e

        if completed.returncode != 0:
            # Nếu stdout có JSON chứa trường error thì ưu tiên hiển thị thông báo đó
            err_detail = (completed.stderr or completed.stdout).strip()
            try:
                err_json = json.loads(completed.stdout)
                if isinstance(err_json, dict) and err_json.get("error"):
                    err_detail = str(err_json["error"])
            except json.JSONDecodeError:
                pass
            raise AgyCLIError(
                f"Antigravity CLI lỗi (exit {completed.returncode}): {err_detail}"
            )

        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as e:
            raise AgyCLIError(
                f"Không parse được output của Antigravity CLI: {completed.stdout[:500]}"
            ) from e

        if result.get("status") == "ERROR" or result.get("is_error") or result.get("error"):
            err_msg = result.get("error") or result.get("response") or result.get("result")
            raise AgyCLIError(f"Antigravity CLI trả về lỗi: {err_msg}")

        structured = result.get("structured_output")
        if structured is None:
            # Dự phòng: nếu CLI trả về JSON dạng chuỗi trong trường "response" hoặc "result"
            raw_text = (result.get("response") or result.get("result") or "").strip()
            try:
                structured = json.loads(raw_text)
            except json.JSONDecodeError:
                return {"type": "message", "content": raw_text}
        return structured

    def _build_prompt(self, system_prompt: str, context: AgentContext) -> str:
        """Ghép chỉ thị hệ thống, danh sách tool và lịch sử hội thoại thành một prompt văn bản."""
        tools = [self._to_tool_spec(tool) for tool in context.tools]
        conversation = [
            self._to_transcript_entry(message)
            for message in context.history
        ]
        return (
            f"<system>\n{system_prompt}\n</system>\n\n"
            f"<tools>\n{json.dumps(tools, ensure_ascii=False, indent=2)}\n</tools>\n\n"
            f"<conversation>\n{json.dumps(conversation, ensure_ascii=False, indent=2)}\n</conversation>\n\n"
            "Hãy đưa ra quyết định tiếp theo cho lượt của assistant."
        )

    def _to_tool_spec(self, tool: Tool) -> dict:
        """Chuyển đổi Tool domain thành mô tả tool dạng JSON."""
        return {
            "name": tool.tool_name,
            "description": tool.tool_description,
            "parameters": tool.tool_kwargs.model_json_schema(),
        }

    def _to_transcript_entry(self, message: Message) -> dict:
        """Chuyển đổi Message domain thành một mục trong transcript."""
        if isinstance(message, SystemMessage):
            return {"role": "system", "content": message.content}
        if isinstance(message, UserMessage):
            return {"role": "user", "content": parts_to_text(message.content)}
        if isinstance(message, AssistantMessage):
            return {"role": "assistant", "content": parts_to_text(message.content)}
        if isinstance(message, ToolCallMessage):
            return {
                "role": "assistant",
                "tool_calls": [
                    {"id": tc.id, "name": tc.name, "kwargs": tc.kwargs}
                    for tc in message.tool_calls
                ],
            }
        if isinstance(message, ToolResultMessage):
            return {
                "role": "tool",
                "tool_call_id": message.tool_call_id,
                "name": message.name,
                "content": parts_to_text(message.content),
                "is_error": message.is_error,
            }

        raise MessageTypeDoesNotExist(
            f"Đối tượng {type(message).__name__} không phù hợp khi convert sang transcript của Antigravity CLI"
        )

    def _to_decision(self, payload: dict[str, Any]) -> Decision:
        """Chuyển đổi structured output của Antigravity CLI thành Decision domain."""
        tool_calls = payload.get("tool_calls") or []
        if payload.get("type") == "tool_calls" and tool_calls:
            return ToolCallMessage(
                tool_calls=[
                    ToolCallMessage.ToolCall(
                        id=f"call_{uuid.uuid4().hex[:12]}",
                        name=tc["name"],
                        kwargs=tc.get("kwargs") or {},
                    )
                    for tc in tool_calls
                ]
            )

        return AssistantMessage(
            content=[TextPart(payload.get("content") or 'Không có câu trả lời')]
        )
