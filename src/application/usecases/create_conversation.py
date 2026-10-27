"""Use Case Thêm hội thoại - Tạo hội thoại mới cho người dùng đang đăng nhập.
"""

from src.application.repositories import ConversationRepository, SessionRepository
from src.application.usecases.common import authenticate, normalize_title
from src.domain.entities import Conversation

DEFAULT_TITLE = "Hội thoại mới"


class CreateConversationUseCase:
    """Thêm mới một hội thoại."""

    def __init__(self, sessions: SessionRepository, conversations: ConversationRepository):
        self.sessions = sessions
        self.conversations = conversations

    def execute(self, token: str, title: str | None = None) -> Conversation:
        session = authenticate(self.sessions, token)
        return self.conversations.add(Conversation(
            user_id=session.user_id,
            title=normalize_title(title) if title else DEFAULT_TITLE,
        ))
