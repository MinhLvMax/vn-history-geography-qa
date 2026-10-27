"""Use Case Đảm bảo có tài khoản admin - Chạy khi khởi động app, tạo admin từ cấu hình nếu chưa có.
"""

from src.application.repositories import UserRepository
from src.application.security import PasswordHasher
from src.application.usecases.register import MIN_PASSWORD_LENGTH
from src.domain.entities import ROLE_ADMIN, User
from src.domain.exceptions import InvalidInput


class EnsureAdminUseCase:
    """Bảo đảm hệ thống luôn có ít nhất một admin. Gọi nhiều lần vẫn an toàn (idempotent)."""

    def __init__(self, users: UserRepository, password_hasher: PasswordHasher):
        self.users = users
        self.password_hasher = password_hasher

    def execute(self, username: str | None, password: str | None) -> None:
        if self.users.has_role(ROLE_ADMIN):
            return

        username = (username or "").strip()
        if not username or not password:
            raise InvalidInput(
                "Chưa có tài khoản admin. Vui lòng đặt ADMIN_USERNAME và ADMIN_PASSWORD trong file .env"
            )
        if len(password) < MIN_PASSWORD_LENGTH:
            raise InvalidInput(f"ADMIN_PASSWORD phải có ít nhất {MIN_PASSWORD_LENGTH} ký tự")

        existing = self.users.get_by_username(username)
        if existing is not None:
            # Username đã có (vd. đăng ký thường trước đó): nâng quyền, giữ nguyên mật khẩu
            self.users.update_role(existing.id, ROLE_ADMIN)
            return

        self.users.add(User(
            username=username,
            password_hash=self.password_hasher.hash(password),
            display_name="Quản trị viên",
            role=ROLE_ADMIN,
        ))
