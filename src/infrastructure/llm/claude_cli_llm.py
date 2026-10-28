"""Adapter gọi mô hình qua Claude Code CLI."""

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


class ClaudeCLIError(AppError):
    """Lỗi xảy ra khi gọi Claude CLI thất bại hoặc trả về dữ liệu không hợp lệ."""
    pass


# Schema ép Claude trả về quyết định ở dạng JSON có cấu trúc
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
Bạn đang chạy như bộ não của một agent. Mỗi lượt bạn chỉ đưa ra MỘT quyết định:
- Trả lời người dùng: {"type": "message", "content": "<câu trả lời>"}
- Gọi tool: {"type": "tool_calls", "tool_calls": [{"name": "<tên tool>", "kwargs": {...}}]}
Các tool trong <tools> KHÔNG thể gọi trực tiếp: muốn dùng tool, hãy trả về JSON type="tool_calls"
và hệ thống bên ngoài sẽ thực thi giúp bạn. kwargs phải khớp JSON schema của tool.
Kết quả tool sẽ được gửi lại ở lượt sau trong <conversation> với role="tool"."""


class ClaudeCLILLM(LLMPort):
    """Adapter triển khai LLMPort bằng cách gọi `claude -p` qua subprocess."""

    def __init__(
        self,
        model_name: str,
        effort: str | None = None,
        builtin_tools: list[str] | None = None,
        claude_path: str | None = None,
        timeout: float = 300,
        cwd: Path | None = None,
    ):
        self.model_name = model_name
        self.effort = effort
        # Tool built-in của Claude Code (vd. WebSearch, WebFetch) do CLI tự thực thi trong subprocess
        self.builtin_tools = builtin_tools or []
        self.timeout = timeout
        self.cwd = cwd
        self.claude_path = claude_path or shutil.which("claude")
        if not self.claude_path:
            raise ClaudeCLIError(
                "Không tìm thấy lệnh 'claude'. Hãy cài Claude Code và đăng nhập (chạy `claude` một lần)."
            )

    def decide(self, context: AgentContext) -> Decision:
        """Gửi toàn bộ ngữ cảnh cho Claude CLI và chuyển kết quả JSON thành Decision."""
        system_prompt = f"{context.system_prompt}\n\n{_PROTOCOL_INSTRUCTIONS}"
        if self.builtin_tools:
            system_prompt += (
                f"\nNgoài ra bạn được gọi TRỰC TIẾP các tool built-in: {', '.join(self.builtin_tools)}. "
                "Chỉ các tool trong <tools> mới phải gọi qua JSON type=\"tool_calls\"."
            )
        payload = self._run(system_prompt=system_prompt, prompt=self._build_prompt(context))
        return self._to_decision(payload)

    def _run(self, system_prompt: str, prompt: str) -> dict:
        """Chạy Claude CLI ở chế độ non-interactive và trả về structured output."""
        cmd = [
            self.claude_path,
            "-p",
            "--output-format", "json",
            "--json-schema", json.dumps(_DECISION_SCHEMA),
            "--system-prompt", system_prompt,
            "--model", self.model_name,
            "--tools", ",".join(self.builtin_tools),
            "--setting-sources", "",
            "--strict-mcp-config",
            "--no-session-persistence",
        ]
        if self.builtin_tools:
            # Cho phép chạy tool built-in mà không cần hỏi quyền (chế độ -p không thể hỏi)
            cmd += ["--allowedTools", ",".join(self.builtin_tools)]
        if self.effort:
            cmd += ["--effort", self.effort]
        try:
            # Prompt truyền qua stdin để tránh giới hạn độ dài command line trên Windows
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
            raise ClaudeCLIError(f"Claude CLI quá thời gian chờ ({self.timeout}s)") from e

        if completed.returncode != 0:
            raise ClaudeCLIError(
                f"Claude CLI lỗi (exit {completed.returncode}): {completed.stderr or completed.stdout}"
            )

        try:
            result = json.loads(completed.stdout)
        except json.JSONDecodeError as e:
            raise ClaudeCLIError(f"Không parse được output của Claude CLI: {completed.stdout[:500]}") from e

        if result.get("is_error"):
            raise ClaudeCLIError(f"Claude CLI trả về lỗi: {result.get('result')}")

        structured = result.get("structured_output")
        if structured is None:
            # Dự phòng: một số phiên bản chỉ trả JSON dạng chuỗi trong trường "result"
            try:
                structured = json.loads(result.get("result") or "")
            except json.JSONDecodeError:
                return {"type": "message", "content": result.get("result") or ""}
        return structured

    def _build_prompt(self, context: AgentContext) -> str:
        """Ghép danh sách tool và lịch sử hội thoại thành một prompt văn bản."""
        tools = [self._to_tool_spec(tool) for tool in context.tools]
        conversation = [
            self._to_transcript_entry(message)
            for message in context.history
        ]
        return (
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
            f"Đối tượng {type(message).__name__} không phù hợp khi convert sang transcript của Claude CLI"
        )

    def _to_decision(self, payload: dict[str, Any]) -> Decision:
        """Chuyển đổi structured output của Claude thành Decision domain."""
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
