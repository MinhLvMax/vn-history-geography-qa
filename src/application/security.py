"""Giao diện băm và kiểm tra mật khẩu."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class PasswordHasher(Protocol):
    """Băm mật khẩu khi đăng ký và kiểm tra mật khẩu khi đăng nhập."""

    def hash(self, password: str) -> str:
        """Băm mật khẩu thành chuỗi có thể lưu trữ."""
        ...

    def verify(self, password: str, password_hash: str) -> bool:
        """Kiểm tra mật khẩu có khớp với chuỗi đã băm không."""
        ...
