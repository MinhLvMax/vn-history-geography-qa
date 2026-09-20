from src.history_agent.app.tool_manager import ToolManager
from src.history_agent.app.model_reasoner import ModelReasoner
from src.history_agent.dom.context import Context
from src.history_agent.dom.decision.final_decision import FinalDecision
from src.history_agent.dom.decision.tool_call_decision import ToolCallDecision
from src.history_agent.config import Config


class Agent:
    def __init__(
            self,
            model_reasoner: ModelReasoner | None = None,
            tool_manager: ToolManager | None = None
    ):
        self.model_reasoner = model_reasoner
        self.tool_manager = tool_manager

    def invoke(self, context: Context) -> str:
        while True:
            Config.logger.debug('Vòng lặp suy nghĩa của agent')

            decision = self.model_reasoner.decide(
                context=context,
                tools=self.tool_manager.tools
            )
            '''Ra quyết định'''

            if isinstance(decision, FinalDecision):
                '''Trả lời được ngay thì trả lời luôn'''
                context.add_final_message(
                    content=decision.final_content,
                )
                return decision.final_content

            if isinstance(decision, ToolCallDecision):
                '''Cần gọi tool thì thực thi từng tool và thêm kết quả vào bối cảnh'''
                context.add_tool_call_message(
                    tool_calls=decision.tool_calls
                )
                for call in decision.tool_calls:
                    Config.logger.debug(f'Gọi tool {call.name} {call.kwargs}')

                    tool_result = self.tool_manager.execute_tool(
                        tool_name=call.name,
                        **call.kwargs,
                    )
                    Config.logger.debug(f'Kết quả của {call.name}: {tool_result.to_text()}')

                    context.add_tool_result_message(
                        id=call.tool_call_id,
                        result=tool_result.to_text(),
                        tool_name=call.name
                    )
