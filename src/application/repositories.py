"""Application Repositories - Các cổng (Port) lưu trữ người dùng, hội thoại và tin nhắn.

Tầng Application chỉ biết các hợp đồng này; việc lưu vào SQLite / PostgreSQL / ...
do các adapter ở tầng Infrastructure đảm nhiệm.
"""

from typing import Protocol, runtime_checkable

from src.domain.entities import AuthSession, Conversation, ConversationMessage, LlmModel, User
from src.domain.models import Message


@runtime_checkable
class UserRepository(Protocol):
    """Kho lưu trữ người dùng."""

    def add(self, user: User) -> User:
        """Thêm người dùng mới (ném EntityAlreadyExists nếu trùng username)."""
        ...

    def get(self, user_id: str) -> User | None:
        """Lấy người dùng theo ID."""
        ...

    def get_by_username(self, username: str) -> User | None:
        """Lấy người dùng theo username."""
        ...

    def list_all(self) -> list[User]:
        """Lấy toàn bộ người dùng."""
        ...

    def has_role(self, role: str) -> bool:
        """Kiểm tra đã có ít nhất một người dùng với role này chưa."""
        ...

    def update_role(self, user_id: str, role: str) -> None:
        """Đổi role của người dùng (ném EntityNotFound nếu không tồn tại)."""
        ...

    def update_ui_config(self, user_id: str, ui_config: dict) -> None:
        """Ghi đè trạng thái giao diện của người dùng (ném EntityNotFound nếu không tồn tại)."""
        ...


@runtime_checkable
class ConversationRepository(Protocol):
    """Kho lưu trữ hội thoại."""

    def add(self, conversation: Conversation) -> Conversation:
        """Thêm hội thoại mới."""
        ...

    def get(self, conversation_id: str) -> Conversation | None:
        """Lấy hội thoại theo ID."""
        ...

    def list_by_user(self, user_id: str) -> list[Conversation]:
        """Lấy các hội thoại của một người dùng, mới cập nhật nhất đứng trước."""
        ...

    def update(self, conversation: Conversation) -> Conversation:
        """Cập nhật tiêu đề / thời điểm cập nhật (ném EntityNotFound nếu không tồn tại)."""
        ...

    def delete(self, conversation_id: str) -> None:
        """Xóa hội thoại cùng toàn bộ tin nhắn của nó."""
        ...


@runtime_checkable
class MessageRepository(Protocol):
    """Kho lưu trữ tin nhắn trong hội thoại."""

    def add(self, conversation_id: str, message: Message) -> ConversationMessage:
        """Thêm một tin nhắn vào cuối hội thoại."""
        ...

    def add_many(self, conversation_id: str, messages: list[Message]) -> list[ConversationMessage]:
        """Thêm nhiều tin nhắn vào cuối hội thoại theo đúng thứ tự (vd. cả một lượt ReAct)."""
        ...

    def list_by_conversation(self, conversation_id: str) -> list[ConversationMessage]:
        """Lấy toàn bộ tin nhắn của hội thoại theo thứ tự."""
        ...


@runtime_checkable
class ModelRepository(Protocol):
    """Kho lưu trữ danh mục model LLM."""

    def list_all(self) -> list[LlmModel]:
        """Lấy toàn bộ model, sắp theo tên hiển thị."""
        ...

    def get(self, model_id: str) -> LlmModel | None:
        """Lấy model theo ID."""
        ...

    def get_by_provider_code(self, provider: str, model_code: str) -> LlmModel | None:
        """Lấy model theo cặp (nhà cung cấp, tên chuẩn)."""
        ...

    def get_default(self) -> LlmModel | None:
        """Lấy model đang đặt mặc định (None nếu chưa có)."""
        ...

    def add(self, model: LlmModel) -> LlmModel:
        """Thêm model mới (ném EntityAlreadyExists nếu trùng nhà cung cấp + tên chuẩn)."""
        ...

    def update(self, model: LlmModel) -> LlmModel:
        """Cập nhật model (ném EntityNotFound nếu không tồn tại)."""
        ...

    def delete(self, model_id: str) -> None:
        """Xóa model. Không lỗi nếu không tồn tại."""
        ...

    def clear_default(self, except_id: str | None = None) -> None:
        """Bỏ đánh dấu mặc định của mọi model (trừ model có except_id)."""
        ...


@runtime_checkable
class SessionRepository(Protocol):
    """Kho lưu trữ phiên đăng nhập."""

    def add(self, session: AuthSession) -> AuthSession:
        """Lưu phiên đăng nhập mới."""
        ...

    def get(self, token: str) -> AuthSession | None:
        """Lấy phiên theo token."""
        ...

    def delete(self, token: str) -> None:
        """Xóa phiên (đăng xuất). Không lỗi nếu phiên không tồn tại."""
        ...
