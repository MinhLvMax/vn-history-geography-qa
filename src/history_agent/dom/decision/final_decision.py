from dataclasses import dataclass
from src.history_agent.dom.decision import Decision


@dataclass
class FinalDecision(Decision):
    final_content: str
