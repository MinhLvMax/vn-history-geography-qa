"""Use Case Đăng nhập - Kiểm tra username/mật khẩu và cấp phiên đăng nhập.
"""

import secrets
from datetime import timedelta

from src.application.repositories import SessionRepository, UserRepository
from src.application.security import PasswordHasher
from src.domain.entities import AuthSession, utcnow
from src.domain.exceptions import InvalidCredentials


class LoginUseCase:
    """Đăng nhập bằng username + mật khẩu, trả về phiên chứa token."""

    def __init__(
        self,
        users: UserRepository,
        sessions: SessionRepository,
        password_hasher: PasswordHasher,
        session_ttl: timedelta = timedelta(days=7),
    ):
        self.users = users
        self.sessions = sessions
        self.password_hasher = password_hasher
        self.session_ttl = session_ttl

    def execute(self, username: str, password: str) -> AuthSession:
        user = self.users.get_by_username((username or "").strip())
        # Cùng một thông báo cho cả sai username lẫn sai mật khẩu để không lộ username nào tồn tại
        if user is None or not self.password_hasher.verify(password or "", user.password_hash):
            raise InvalidCredentials("Sai username hoặc mật khẩu")

        return self.sessions.add(AuthSession(
            token=secrets.token_urlsafe(32),
            user_id=user.id,
            expires_at=utcnow() + self.session_ttl,
        ))
