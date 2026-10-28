"""Đăng ký tài khoản người dùng mới."""

from src.application.repositories import UserRepository
from src.application.security import PasswordHasher
from src.domain.entities import User
from src.domain.exceptions import EntityAlreadyExists, InvalidInput

MIN_PASSWORD_LENGTH = 6


class RegisterUseCase:
    """Đăng ký tài khoản mới."""

    def __init__(self, users: UserRepository, password_hasher: PasswordHasher):
        self.users = users
        self.password_hasher = password_hasher

    def execute(self, username: str, password: str, display_name: str | None = None) -> User:
        username = (username or "").strip()
        if not username:
            raise InvalidInput("Username không được để trống")
        if len(password or "") < MIN_PASSWORD_LENGTH:
            raise InvalidInput(f"Mật khẩu phải có ít nhất {MIN_PASSWORD_LENGTH} ký tự")
        if self.users.get_by_username(username) is not None:
            raise EntityAlreadyExists(f"Username '{username}' đã tồn tại")

        return self.users.add(User(
            username=username,
            password_hash=self.password_hasher.hash(password),
            display_name=display_name,
        ))
