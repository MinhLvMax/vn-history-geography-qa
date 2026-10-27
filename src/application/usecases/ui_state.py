"""Use Case Trạng thái giao diện - Đọc / lưu hội thoại, provider, model, suy luận, tool built-in của người dùng.
"""

from typing import Any

from src.application.repositories import SessionRepository, UserRepository
from src.application.usecases.common import authenticate
from src.domain.exceptions import Unauthorized

# Các khóa được phép lưu; mọi khóa khác bị bỏ qua để không ghi dữ liệu rác vào CSDL
UI_STATE_KEYS = ("conversation_id", "provider", "model", "reasoning", "builtin_enabled", "builtin_tools")


class GetUiStateUseCase:
    """Lấy trạng thái giao diện đã lưu của người dùng đang đăng nhập."""

    def __init__(self, sessions: SessionRepository, users: UserRepository):
        self.sessions = sessions
        self.users = users

    def execute(self, token: str) -> dict[str, Any]:
        session = authenticate(self.sessions, token)
        user = self.users.get(session.user_id)
        if user is None:
            raise Unauthorized("Tài khoản không còn tồn tại, vui lòng đăng nhập lại")
        return dict(user.ui_config or {})


class SaveUiStateUseCase:
    """Ghi trạng thái giao diện của người dùng đang đăng nhập (chỉ giữ các khóa hợp lệ)."""

    def __init__(self, sessions: SessionRepository, users: UserRepository):
        self.sessions = sessions
        self.users = users

    def execute(self, token: str, ui_state: dict[str, Any]) -> None:
        session = authenticate(self.sessions, token)
        clean = {key: ui_state[key] for key in UI_STATE_KEYS if key in ui_state}
        self.users.update_ui_config(session.user_id, clean)
