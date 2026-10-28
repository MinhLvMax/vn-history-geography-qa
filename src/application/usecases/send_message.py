"""Tiếp nhận tin nhắn, điều phối Agent suy luận và lưu kết quả."""

from dataclasses import dataclass, replace

from src.application.agent_service import AgentServiceFactory
from src.application.approval import ApprovalPort
from src.application.context_strategy import ContextStrategyPort, NoOpContextStrategy
from src.application.repositories import (
    ConversationRepository,
    MessageRepository,
    SessionRepository,
)
from src.application.usecases.common import authenticate, get_owned_conversation
from src.domain.entities import utcnow
from src.domain.exceptions import InvalidInput
from src.domain.models import AgentContext, AssistantMessage, Message, TextPart, UserMessage
from src.domain.ports import Tool


@dataclass
class SendMessageResult:
    """Kết quả một lượt gửi tin nhắn."""
    new_messages: list[Message]  # Tin nhắn của người dùng + các bước tool + câu trả lời cuối
    reply: AssistantMessage


class SendMessageUseCase:
    """Gửi tin nhắn của người dùng vào một hội thoại và nhận câu trả lời từ Agent.

    Chỉ khi Agent chạy thành công thì cả lượt (tin nhắn người dùng + các bước tool + câu trả lời)
    mới được lưu, để lịch sử không bị lệch khi LLM lỗi.
    """

    def __init__(
        self,
        sessions: SessionRepository,
        conversations: ConversationRepository,
        messages: MessageRepository,
        agent_service_factory: AgentServiceFactory,
        tools: list[Tool],
        system_prompt: str,
        context_strategy: ContextStrategyPort | None = None,
    ):
        self.sessions = sessions
        self.conversations = conversations
        self.messages = messages
        self.agent_service_factory = agent_service_factory
        self.tools = tools
        self.system_prompt = system_prompt
        self.context_strategy: ContextStrategyPort = context_strategy or NoOpContextStrategy()

    def execute(
        self,
        token: str,
        conversation_id: str,
        text: str,
        provider: str,
        model: str,
        reasoning: str | None = None,
        builtin_tools: list[str] | None = None,
        approver: ApprovalPort | None = None,
    ) -> SendMessageResult:
        session = authenticate(self.sessions, token)
        conversation = get_owned_conversation(self.conversations, conversation_id, session.user_id)
        text = (text or "").strip()
        if not text:
            raise InvalidInput("Tin nhắn không được để trống")

        # Dựng lại ngữ cảnh từ lịch sử đã lưu (qua bộ lọc ContextStrategy) rồi thêm tin nhắn mới
        raw_history = [stored.message for stored in self.messages.list_by_conversation(conversation_id)]
        history = self.context_strategy.prepare_history(raw_history)
        context = AgentContext(system_prompt=self.system_prompt, history=history, tools=self.tools)
        start_index = len(context.history)
        context.add_message(UserMessage(content=[TextPart(text=text)]))

        agent_service = self.agent_service_factory(provider, model, reasoning, builtin_tools or [])
        agent_service.thinking(context, approver=approver)

        new_messages = context.history[start_index:]
        self.messages.add_many(conversation_id, new_messages)
        self.conversations.update(replace(conversation, updated_at=utcnow()))

        return SendMessageResult(new_messages=new_messages, reply=new_messages[-1])
