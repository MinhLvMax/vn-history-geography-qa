"""Truy xuất danh sách tin nhắn của cuộc trò chuyện."""

from src.application.repositories import (
    ConversationRepository,
    MessageRepository,
    SessionRepository,
)
from src.application.usecases.common import authenticate, get_owned_conversation
from src.domain.models import Message


class GetConversationMessagesUseCase:
    """Lấy tin nhắn của một hội thoại thuộc về người dùng."""

    def __init__(
        self,
        sessions: SessionRepository,
        conversations: ConversationRepository,
        messages: MessageRepository,
    ):
        self.sessions = sessions
        self.conversations = conversations
        self.messages = messages

    def execute(self, token: str, conversation_id: str) -> list[Message]:
        session = authenticate(self.sessions, token)
        get_owned_conversation(self.conversations, conversation_id, session.user_id)
        return [stored.message for stored in self.messages.list_by_conversation(conversation_id)]
