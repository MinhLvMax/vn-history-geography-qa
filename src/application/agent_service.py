"""Dịch vụ điều phối vòng lặp suy luận ReAct của Agent."""

from typing import Callable

from src.application.approval import ApprovalPort, approval_scope
from src.application.tool_service import ToolExecutorService
from src.domain.models import (
    AgentContext,
    AgentThinkingResult,
    AssistantMessage,
    TextPart,
    ToolCallMessage,
    ToolResultMessage,
)
from src.domain.ports import LLMPort, LoggerPort, NullLogger


class AgentService:
    """Use Case điều phối vòng lặp suy luận (Thinking / ReAct Loop) của Agent."""

    def __init__(
        self,
        llm: LLMPort,
        tool_executor: ToolExecutorService,
        logger: LoggerPort | None = None,
        max_steps: int = 25,
    ):
        self.llm = llm
        self.tool_executor = tool_executor
        self.logger: LoggerPort = logger or NullLogger()
        # Số bước gọi tool tối đa cho một câu hỏi, tránh Agent gọi tool liên tục không dừng
        self.max_steps = max_steps

    def thinking(
        self, agent_context: AgentContext, approver: ApprovalPort | None = None
    ) -> AgentThinkingResult:
        """Thực hiện vòng lặp ReAct cho đến khi nhận được phản hồi hoàn chỉnh từ LLM.

        approver: giao diện xin xác nhận của người dùng cho các thao tác nhạy cảm của tool
        (vd. ghi ra ngoài workspace). Không có thì các thao tác đó bị từ chối.
        """
        self.logger.info("Bắt đầu chu trình suy luận (ReAct loop)")
        step = 0

        while True:
            step += 1
            self.logger.debug(f"Bước suy luận #{step}: Gửi ngữ cảnh tới LLM để đưa ra quyết định")
            decision = self.llm.decide(agent_context)

            if isinstance(decision, ToolCallMessage):
                self.logger.info(
                    f"Bước #{step}: LLM yêu cầu gọi {len(decision.tool_calls)} tool(s)"
                )
                # Lưu quyết định gọi tool của Assistant vào lịch sử trò chuyện
                agent_context.add_message(decision)

                # Thực thi từng tool call và lưu kết quả trả về vào context
                with approval_scope(approver):
                    for tool_call in decision.tool_calls:
                        agent_context.add_message(self._run_tool_call(tool_call))

                if step >= self.max_steps:
                    self.logger.warning(f"Dừng chu trình suy luận vì vượt quá {self.max_steps} bước")
                    agent_context.add_message(AssistantMessage(content=[TextPart(
                        f"Mình đã dừng lại vì vượt quá giới hạn {self.max_steps} bước xử lý cho một câu hỏi. "
                        "Bạn có thể thu hẹp yêu cầu hoặc bảo mình làm tiếp."
                    )]))
                    return AgentThinkingResult(messages=agent_context.history)

            elif isinstance(decision, AssistantMessage):
                self.logger.info(f"Bước #{step}: LLM đã hoàn tất phản hồi, kết thúc chu trình suy luận")
                # Lưu câu trả lời hoàn tất của Assistant và kết thúc chu trình suy luận
                agent_context.add_message(decision)
                return AgentThinkingResult(messages=agent_context.history)

    def _run_tool_call(self, tool_call: ToolCallMessage.ToolCall) -> ToolResultMessage:
        """Chạy một tool call. Lỗi không làm hỏng cả lượt mà được gửi lại cho LLM để nó tự xử lý."""
        self.logger.debug(f"Thực thi tool call id='{tool_call.id}', name='{tool_call.name}'")
        try:
            content = self.tool_executor.execute_a_tool(tool_name=tool_call.name, **tool_call.kwargs)
            return ToolResultMessage(tool_call_id=tool_call.id, name=tool_call.name, content=content)
        except Exception as exc:  # noqa: BLE001 - mọi lỗi của tool đều phải báo lại cho LLM
            self.logger.warning(f"Tool '{tool_call.name}' lỗi: {exc}")
            return ToolResultMessage(
                tool_call_id=tool_call.id,
                name=tool_call.name,
                content=[TextPart(f"Lỗi khi chạy tool '{tool_call.name}': {exc}")],
                is_error=True,
            )


# Factory tạo AgentService theo lựa chọn (provider, model, reasoning, builtin_tools) từ giao diện
AgentServiceFactory = Callable[[str, str, str | None, list[str]], AgentService]
