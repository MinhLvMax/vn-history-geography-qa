"""Use Case Danh sách hội thoại - Các hội thoại của người dùng đang đăng nhập.
"""

from src.application.repositories import ConversationRepository, SessionRepository
from src.application.usecases.common import authenticate
from src.domain.entities import Conversation


class ListConversationsUseCase:
    """Liệt kê hội thoại của người dùng, mới cập nhật nhất đứng trước."""

    def __init__(self, sessions: SessionRepository, conversations: ConversationRepository):
        self.sessions = sessions
        self.conversations = conversations

    def execute(self, token: str) -> list[Conversation]:
        session = authenticate(self.sessions, token)
        return self.conversations.list_by_user(session.user_id)
