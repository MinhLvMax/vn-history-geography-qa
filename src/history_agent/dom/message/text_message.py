from dataclasses import dataclass
from src.history_agent.dom.message import BaseMessage


@dataclass
class TextMessage(BaseMessage):
    content: str
