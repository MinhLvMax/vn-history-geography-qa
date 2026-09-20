from dataclasses import dataclass
from src.history_agent.dom.message import BaseMessage


@dataclass
class ToolResultMessage(BaseMessage):
    tool_call_id: str
    tool_result: str
    tool_name: str
