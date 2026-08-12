from src.history_agent.domain.state import State, ToolResult, Message
from src.history_agent.domain.decision import Decision, DecisionType
from src.history_agent.domain.format.decision_prompt import DecisionPrompt
from src.history_agent.application.ports.llm_port import LLM
from src.history_agent.application.tool_registry import ToolRegistry


class Agent:
    def __init__(self, llm: LLM, tool_registry: ToolRegistry):
        self.llm = llm
        self.tool_registry = tool_registry
        self.state = State()
        pass

    def _decide(self, state: State) -> Decision:
        # Dựng prompt quyết định dựa trên lịch sử chat, kết quả công cụ
        prompt = DecisionPrompt(
            messages=state.get_messages()[:3],
            tool_results=state.get_tool_results()[:2],
            tools=self.tool_registry.tools_describe()
        )
        return self.llm.complete(
            messages=prompt,
            response_model=Decision,
        )

    def _execute(self, tool_decision: Decision) -> ToolResult:

        pass

    def run(self, message):
        self.state.messages.append(
            Message(
                role='user',
                content=message
            )
        )
        while True:
            decision = self._decide(self.state)
            if decision.type == DecisionType.FINAL:
                self.state.messages.append(
                    Message(
                        role='assistant',
                        content=decision.answer,
                    )
                )
                return decision.answer

            if decision.type == DecisionType.TOOL:
                result = self._execute(decision)
                self.state.tool_results.append(result)
