"""Đổi tên tiêu đề cuộc trò chuyện."""

from dataclasses import replace

from src.application.repositories import ConversationRepository, SessionRepository
from src.application.usecases.common import (
    authenticate,
    get_owned_conversation,
    normalize_title,
)
from src.domain.entities import Conversation, utcnow


class RenameConversationUseCase:
    """Đổi tên một hội thoại thuộc về người dùng."""

    def __init__(self, sessions: SessionRepository, conversations: ConversationRepository):
        self.sessions = sessions
        self.conversations = conversations

    def execute(self, token: str, conversation_id: str, new_title: str) -> Conversation:
        session = authenticate(self.sessions, token)
        conversation = get_owned_conversation(self.conversations, conversation_id, session.user_id)
        return self.conversations.update(
            replace(conversation, title=normalize_title(new_title), updated_at=utcnow())
        )
