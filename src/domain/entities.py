"""Thực thể nghiệp vụ lõi của hệ thống."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.domain.models import Message


def new_id() -> str:
    """Sinh ID dạng chuỗi UUID (không phụ thuộc cơ chế autoincrement của từng CSDL)."""
    return str(uuid.uuid4())


def utcnow() -> datetime:
    """Thời điểm hiện tại theo UTC."""
    return datetime.now(timezone.utc)


ROLE_USER = "user"
ROLE_ADMIN = "admin"


@dataclass
class User:
    """Người dùng của hệ thống."""
    username: str
    password_hash: str
    display_name: str | None = None
    role: str = ROLE_USER
    # Trạng thái giao diện lần trước (hội thoại, provider, model, suy luận, tool built-in)
    ui_config: dict | None = None
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)

    @property
    def is_admin(self) -> bool:
        """Người dùng có quyền quản trị hay không."""
        return self.role == ROLE_ADMIN


@dataclass
class LlmModel:
    """Một model LLM được phép sử dụng, do quản trị viên khai báo trong CSDL."""
    provider: str
    display_name: str
    model_code: str  # Tên chuẩn gửi lên API
    reasoning_modes: list[str] = field(default_factory=list)
    default_reasoning: str | None = None
    builtin_tools: list[str] = field(default_factory=list)
    is_enabled: bool = True
    is_default: bool = False
    notes: str | None = None
    last_test_at: datetime | None = None
    last_test_ok: bool | None = None
    last_test_report: list[dict] | None = None
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


@dataclass
class AuthSession:
    """Phiên đăng nhập: token cấp cho người dùng sau khi đăng nhập thành công."""
    token: str
    user_id: str
    expires_at: datetime
    created_at: datetime = field(default_factory=utcnow)

    def is_expired(self, now: datetime | None = None) -> bool:
        """Phiên đã hết hạn hay chưa."""
        return (now or utcnow()) >= self.expires_at


@dataclass
class Conversation:
    """Một hội thoại thuộc về một người dùng."""
    user_id: str
    title: str = "Hội thoại mới"
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)


@dataclass
class ConversationMessage:
    """Một tin nhắn đã lưu: bọc domain Message kèm vị trí của nó trong hội thoại."""
    conversation_id: str
    message: Message
    position: int = 0  # Thứ tự trong hội thoại, repository tự gán khi thêm
    id: str = field(default_factory=new_id)
    created_at: datetime = field(default_factory=utcnow)
