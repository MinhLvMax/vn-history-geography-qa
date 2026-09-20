from dataclasses import dataclass
from src.history_agent.dom.message import BaseMessage
from src.history_agent.dom.tool_call import ToolCall


@dataclass
class ToolCallMessage(BaseMessage):
    list_tool_call: list[ToolCall]
