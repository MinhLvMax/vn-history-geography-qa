"""Use Case Đăng xuất - Hủy phiên đăng nhập.
"""

from src.application.repositories import SessionRepository


class LogoutUseCase:
    """Đăng xuất: xóa phiên ứng với token (gọi lại nhiều lần vẫn an toàn)."""

    def __init__(self, sessions: SessionRepository):
        self.sessions = sessions

    def execute(self, token: str) -> None:
        if token:
            self.sessions.delete(token)
