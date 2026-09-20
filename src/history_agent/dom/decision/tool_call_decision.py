from dataclasses import dataclass
from src.history_agent.dom.decision import Decision
from src.history_agent.dom.tool_call import ToolCall


@dataclass
class ToolCallDecision(Decision):
    tool_calls: list[ToolCall]
