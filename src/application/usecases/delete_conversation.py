"""Use Case Xóa hội thoại - Xóa hội thoại (kèm toàn bộ tin nhắn) của người dùng đang đăng nhập.
"""

from src.application.repositories import ConversationRepository, SessionRepository
from src.application.usecases.common import authenticate, get_owned_conversation


class DeleteConversationUseCase:
    """Xóa một hội thoại thuộc về người dùng."""

    def __init__(self, sessions: SessionRepository, conversations: ConversationRepository):
        self.sessions = sessions
        self.conversations = conversations

    def execute(self, token: str, conversation_id: str) -> None:
        session = authenticate(self.sessions, token)
        get_owned_conversation(self.conversations, conversation_id, session.user_id)
        self.conversations.delete(conversation_id)
