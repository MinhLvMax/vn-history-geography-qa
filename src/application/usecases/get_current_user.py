"""Use Case Lấy người dùng hiện tại - Từ token đăng nhập trả về thông tin người dùng.
"""

from src.application.repositories import SessionRepository, UserRepository
from src.application.usecases.common import authenticate
from src.domain.entities import User
from src.domain.exceptions import Unauthorized


class GetCurrentUserUseCase:
    """Lấy người dùng ứng với phiên đăng nhập."""

    def __init__(self, sessions: SessionRepository, users: UserRepository):
        self.sessions = sessions
        self.users = users

    def execute(self, token: str) -> User:
        session = authenticate(self.sessions, token)
        user = self.users.get(session.user_id)
        if user is None:
            raise Unauthorized("Tài khoản không còn tồn tại, vui lòng đăng nhập lại")
        return user
