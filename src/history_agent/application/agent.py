from src.agent_search.domain.state import State, ToolResult, Role, Message
from src.agent_search.domain.decision import Decision, DecisionType
from src.agent_search.domain.format.decision_prompt import DecisionPrompt
from src.agent_search.application.llm_service import LLM
from src.agent_search.application.tool_registry import ToolRegistry


class Agent:
    def __init__(self, llm: LLM, tool_registry: ToolRegistry):
        self.llm = llm
        self.tool_registry = tool_registry
        self.state = State()
        pass

    def _decide(self, state: State) -> Decision:
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
        if message is not None:
            self.state.messages.append(
                Message(
                    role=Role.USER,
                    content=message
                )
            )
        decision = self._decide(self.state)
        if decision.type == DecisionType.FINAL:
            self.state.messages.append(
                Message(
                    role=Role.ASSISTANT,
                    content=decision.answer,
                )
            )
            return decision.answer

        if decision.type == DecisionType.TOOL:
            result = self._execute(decision)

            self.state.tool_results.append(result)

            return self.run(None)
