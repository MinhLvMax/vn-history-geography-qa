"""Adapter kết nối dịch vụ Groq Cloud API."""

import json
from typing import Any
from groq import Groq

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


class GroqLLM(LLMPort):
    """Adapter triển khai LLMPort sử dụng Groq SDK."""

    def __init__(
        self,
        api_key: str,
        model_name: str,
        reasoning_effort: str | None = None,
        builtin_tools: list[str] | None = None,
    ):
        self.model_name = model_name
        self.reasoning_effort = reasoning_effort
        # Tool built-in (vd. browser_search, code_interpreter) do Groq tự thực thi phía server
        self.builtin_tools = builtin_tools or []
        self.client = Groq(api_key=api_key)

    def decide(self, context: AgentContext) -> Decision:
        """Gửi prompt và ngữ cảnh lên Groq API để nhận phản hồi hoặc tool call."""
        messages = [self._to_groq_message(message) for message in context.get_messages()]
        tools = [self._to_groq_tool(tool) for tool in context.tools]
        tools += [{"type": name} for name in self.builtin_tools]

        kwargs: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        if self.reasoning_effort:
            kwargs["reasoning_effort"] = self.reasoning_effort

        response = self.client.chat.completions.create(**kwargs)
        response_message = response.choices[0].message

        if response_message.tool_calls:
            return ToolCallMessage(
                tool_calls=[
                    self._from_groq_tool_call(tool_call)
                    for tool_call in response_message.tool_calls
                ]
            )

        return AssistantMessage(
            content=[TextPart(response_message.content or 'Không có câu trả lời')]
        )

    def _to_groq_tool(self, tool: Tool) -> dict:
        """Chuyển đổi Tool domain thành schema function của Groq/OpenAI."""
        return {
            "type": "function",
            "function": {
                "name": tool.tool_name,
                "description": tool.tool_description,
                "parameters": tool.tool_kwargs.model_json_schema(),
            },
        }

    def _to_groq_message(self, message: Message) -> dict:
        """Chuyển đổi Message domain thành định dạng message của Groq/OpenAI."""
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
                "tool_call_id": message.tool_call_id,
                "name": message.name,
                "content": parts_to_text(message.content),
            }
        if isinstance(message, ToolCallMessage):
            return {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.name,
                            "arguments": json.dumps(
                                tool_call.kwargs, ensure_ascii=False
                            ),
                        },
                    }
                    for tool_call in message.tool_calls
                ],
            }

        raise MessageTypeDoesNotExist(
            f"Đối tượng {type(message).__name__} không phù hợp khi convert sang message của Groq"
        )

    def _from_groq_tool_call(self, tc: Any) -> ToolCallMessage.ToolCall:
        """Chuyển đổi tool call nhận từ Groq sang domain ToolCall."""
        return ToolCallMessage.ToolCall(
            id=tc.id,
            name=tc.function.name,
            kwargs=json.loads(tc.function.arguments or "{}"),
        )


# Alias tương thích ngược với tên gọi cũ
GropLLM = GroqLLM
