'''Dịch ngôn gữ của tầng trình bày thành ngôn ngữ app và domain dùng'''
from src.history_agent.dom.context import Context
from src.history_agent.dom.message import BaseMessage
from src.history_agent.dom.message.text_message import TextMessage
from src.history_agent.dom.message.tool_call_message import ToolCallMessage
from src.history_agent.dom.message.tool_result_message import ToolResultMessage
from src.history_agent.pre.agent.agent_request import (
    AgentRequest,
    TextMessageRequest,
    ToolCallMessageRequest,
    ToolResultMessageRequest,
)


class AgentMapper:

    def to_context(self, request: AgentRequest) -> Context:
        messages = [
            self._to_domain_message(message)
            for message in request.messages
        ]
        return Context(messages=messages)

    def _to_domain_message(
            self,
            message_request: (
                    TextMessageRequest
                    | ToolCallMessageRequest
                    | ToolResultMessageRequest
            ),
    ) -> BaseMessage:

        if isinstance(message_request, TextMessageRequest):
            return TextMessage(
                role=message_request.role,
                content=message_request.content
            )

        if isinstance(message_request, ToolCallMessageRequest):
            return ToolCallMessage(
                role='assistant',
                list_tool_call=message_request.list_tool_call
            )

        if isinstance(message_request, ToolResultMessageRequest):
            return ToolResultMessage(
                role='tool',
                tool_call_id=message_request.tool_call_id,
                tool_name=message_request.tool_name,
                tool_result=message_request.tool_result,
            )

        raise TypeError(
            f"Unsupported message type: {type(message_request).__name__}"
        )
