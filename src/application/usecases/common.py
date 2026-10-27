"""Use Case Common - Các bước kiểm tra dùng chung giữa các use case.
"""

from src.application.repositories import ConversationRepository, SessionRepository
from src.domain.entities import AuthSession, Conversation, User
from src.domain.exceptions import EntityNotFound, InvalidInput, PermissionDenied, Unauthorized

MAX_TITLE_LENGTH = 255


def authenticate(sessions: SessionRepository, token: str) -> AuthSession:
    """Kiểm tra token đăng nhập, trả về phiên hợp lệ (phiên hết hạn sẽ bị xóa)."""
    session = sessions.get(token) if token else None
    if session is None:
        raise Unauthorized("Phiên đăng nhập không hợp lệ, vui lòng đăng nhập lại")
    if session.is_expired():
        sessions.delete(token)
        raise Unauthorized("Phiên đăng nhập đã hết hạn, vui lòng đăng nhập lại")
    return session


def require_admin(user: User) -> None:
    """Chỉ cho phép admin thực hiện thao tác quản trị."""
    if not user.is_admin:
        raise PermissionDenied("Chỉ quản trị viên mới được thực hiện thao tác này")


def get_owned_conversation(
        conversations: ConversationRepository, conversation_id: str, user_id: str
) -> Conversation:
    """Lấy hội thoại và đảm bảo nó thuộc về người dùng đang đăng nhập."""
    conversation = conversations.get(conversation_id)
    if conversation is None:
        raise EntityNotFound(f"Không tìm thấy hội thoại '{conversation_id}'")
    if conversation.user_id != user_id:
        raise PermissionDenied("Bạn không có quyền thao tác trên hội thoại này")
    return conversation


def normalize_title(title: str) -> str:
    """Chuẩn hóa tiêu đề hội thoại (không rỗng, không quá dài)."""
    title = (title or "").strip()
    if not title:
        raise InvalidInput("Tiêu đề hội thoại không được để trống")
    if len(title) > MAX_TITLE_LENGTH:
        raise InvalidInput(f"Tiêu đề hội thoại tối đa {MAX_TITLE_LENGTH} ký tự")
    return title
