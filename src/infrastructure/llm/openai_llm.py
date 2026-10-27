"""Infrastructure LLM - Adapter kết nối với OpenAI qua Responses API.

Dùng Responses API (thay vì Chat Completions) vì chỉ API này hỗ trợ các tool built-in
như `web_search`, `code_interpreter` do OpenAI tự thực thi phía server.

Lưu ý: adapter chạy không trạng thái (`store=False`), lịch sử do hệ thống tự quản lý.
Các "reasoning item" của model suy luận không được lưu lại giữa các lượt nên với chuỗi
tool call dài có thể kém tối ưu hơn một chút, nhưng vẫn hoạt động đúng.
"""

import json
from typing import Any

from openai import OpenAI

from src.domain.exceptions import MessageTypeDoesNotExist
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


class OpenAILLM(LLMPort):
    """Adapter triển khai LLMPort sử dụng OpenAI Responses API."""

    def __init__(
        self,
        api_key: str,
        model_name: str,
        reasoning_effort: str | None = None,
        builtin_tools: list[str] | None = None,
    ):
        self.model_name = model_name
        self.reasoning_effort = reasoning_effort
        # Tool built-in (vd. web_search, code_interpreter) do OpenAI tự thực thi phía server
        self.builtin_tools = builtin_tools or []
        self.client = OpenAI(api_key=api_key)

    def decide(self, context: AgentContext) -> Decision:
        """Gửi ngữ cảnh lên OpenAI để nhận câu trả lời hoặc yêu cầu gọi tool."""
        input_items: list[dict] = []
        for message in context.history:
            input_items.extend(self._to_openai_items(message))

        tools = [self._to_openai_tool(tool) for tool in context.tools]
        tools += [self._to_builtin_tool(name) for name in self.builtin_tools]

        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "instructions": context.system_prompt,
            "input": input_items,
            "store": False,
        }
        if tools:
            kwargs["tools"] = tools
        if self.reasoning_effort:
            kwargs["reasoning"] = {"effort": self.reasoning_effort}

        response = self.client.responses.create(**kwargs)

        function_calls = [item for item in response.output if item.type == "function_call"]
        if function_calls:
            return ToolCallMessage(
                tool_calls=[
                    ToolCallMessage.ToolCall(
                        id=item.call_id,
                        name=item.name,
                        kwargs=json.loads(item.arguments or "{}"),
                    )
                    for item in function_calls
                ]
            )

        return AssistantMessage(
            content=[TextPart(response.output_text or 'Không có câu trả lời')]
        )

    def _to_openai_tool(self, tool: Tool) -> dict:
        """Chuyển đổi Tool domain thành function tool của Responses API."""
        return {
            "type": "function",
            "name": tool.tool_name,
            "description": tool.tool_description,
            "parameters": tool.tool_kwargs.model_json_schema(),
        }

    def _to_builtin_tool(self, name: str) -> dict:
        """Chuyển tên tool built-in thành cấu hình tool của Responses API."""
        if name == "code_interpreter":
            return {"type": "code_interpreter", "container": {"type": "auto"}}
        return {"type": name}

    def _to_openai_items(self, message: Message) -> list[dict]:
        """Chuyển đổi Message domain thành các input item của Responses API."""
        if isinstance(message, SystemMessage):
            return [{"role": "system", "content": message.content}]
        if isinstance(message, UserMessage):
            return [{"role": "user", "content": parts_to_text(message.content)}]
        if isinstance(message, AssistantMessage):
            return [{"role": "assistant", "content": parts_to_text(message.content)}]
        if isinstance(message, ToolCallMessage):
            return [
                {
                    "type": "function_call",
                    "call_id": tool_call.id,
                    "name": tool_call.name,
                    "arguments": json.dumps(tool_call.kwargs, ensure_ascii=False),
                }
                for tool_call in message.tool_calls
            ]
        if isinstance(message, ToolResultMessage):
            return [
                {
                    "type": "function_call_output",
                    "call_id": message.tool_call_id,
                    "output": parts_to_text(message.content),
                }
            ]

        raise MessageTypeDoesNotExist(
            f"Đối tượng {type(message).__name__} không phù hợp khi convert sang input của OpenAI"
        )
