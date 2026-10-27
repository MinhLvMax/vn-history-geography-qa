"""SQLAlchemy Repositories - Adapter triển khai các port lưu trữ của tầng Application.

Chỉ dùng API chung của SQLAlchemy nên chạy được trên mọi CSDL mà SQLAlchemy hỗ trợ.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from src.application.repositories import (
    ConversationRepository,
    MessageRepository,
    ModelRepository,
    SessionRepository,
    UserRepository,
)
from src.domain.entities import AuthSession, Conversation, ConversationMessage, LlmModel, User
from src.domain.exceptions import EntityAlreadyExists, EntityNotFound
from src.domain.models import Message
from src.infrastructure.persistence.sqlalchemy.message_codec import (
    decode_message,
    encode_message,
)
from src.infrastructure.persistence.sqlalchemy.orm_models import (
    ConversationRow,
    MessageRow,
    ModelRow,
    SessionRow,
    UserRow,
)


def _as_utc(value: datetime) -> datetime:
    """Một số CSDL (vd. SQLite) trả về datetime không kèm múi giờ, gắn lại UTC cho nhất quán."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class SqlAlchemyUserRepository(UserRepository):
    """Triển khai UserRepository bằng SQLAlchemy."""

    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def add(self, user: User) -> User:
        try:
            with self._session_factory.begin() as session:
                session.add(UserRow(
                    id=user.id,
                    username=user.username,
                    password_hash=user.password_hash,
                    display_name=user.display_name,
                    role=user.role,
                    ui_config=user.ui_config,
                    created_at=user.created_at,
                ))
        except IntegrityError as e:
            raise EntityAlreadyExists(f"Username '{user.username}' đã tồn tại") from e
        return user

    def get(self, user_id: str) -> User | None:
        with self._session_factory() as session:
            row = session.get(UserRow, user_id)
            return self._to_entity(row) if row else None

    def get_by_username(self, username: str) -> User | None:
        with self._session_factory() as session:
            row = session.scalar(select(UserRow).where(UserRow.username == username))
            return self._to_entity(row) if row else None

    def list_all(self) -> list[User]:
        with self._session_factory() as session:
            rows = session.scalars(select(UserRow).order_by(UserRow.created_at))
            return [self._to_entity(row) for row in rows]

    def has_role(self, role: str) -> bool:
        with self._session_factory() as session:
            return session.scalar(select(UserRow.id).where(UserRow.role == role).limit(1)) is not None

    def update_role(self, user_id: str, role: str) -> None:
        with self._session_factory.begin() as session:
            row = session.get(UserRow, user_id)
            if row is None:
                raise EntityNotFound(f"Không tìm thấy người dùng '{user_id}'")
            row.role = role

    def update_ui_config(self, user_id: str, ui_config: dict) -> None:
        with self._session_factory.begin() as session:
            row = session.get(UserRow, user_id)
            if row is None:
                raise EntityNotFound(f"Không tìm thấy người dùng '{user_id}'")
            row.ui_config = ui_config

    @staticmethod
    def _to_entity(row: UserRow) -> User:
        return User(
            id=row.id,
            username=row.username,
            password_hash=row.password_hash,
            display_name=row.display_name,
            role=row.role,
            ui_config=row.ui_config,
            created_at=_as_utc(row.created_at),
        )


class SqlAlchemyConversationRepository(ConversationRepository):
    """Triển khai ConversationRepository bằng SQLAlchemy."""

    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def add(self, conversation: Conversation) -> Conversation:
        with self._session_factory.begin() as session:
            session.add(ConversationRow(
                id=conversation.id,
                user_id=conversation.user_id,
                title=conversation.title,
                created_at=conversation.created_at,
                updated_at=conversation.updated_at,
            ))
        return conversation

    def get(self, conversation_id: str) -> Conversation | None:
        with self._session_factory() as session:
            row = session.get(ConversationRow, conversation_id)
            return self._to_entity(row) if row else None

    def list_by_user(self, user_id: str) -> list[Conversation]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(ConversationRow)
                .where(ConversationRow.user_id == user_id)
                .order_by(ConversationRow.updated_at.desc())
            )
            return [self._to_entity(row) for row in rows]

    def update(self, conversation: Conversation) -> Conversation:
        with self._session_factory.begin() as session:
            row = session.get(ConversationRow, conversation.id)
            if row is None:
                raise EntityNotFound(f"Không tìm thấy hội thoại '{conversation.id}'")
            row.title = conversation.title
            row.updated_at = conversation.updated_at
        return conversation

    def delete(self, conversation_id: str) -> None:
        with self._session_factory.begin() as session:
            row = session.get(ConversationRow, conversation_id)
            if row is not None:
                session.delete(row)

    @staticmethod
    def _to_entity(row: ConversationRow) -> Conversation:
        return Conversation(
            id=row.id,
            user_id=row.user_id,
            title=row.title,
            created_at=_as_utc(row.created_at),
            updated_at=_as_utc(row.updated_at),
        )


class SqlAlchemyMessageRepository(MessageRepository):
    """Triển khai MessageRepository bằng SQLAlchemy."""

    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def add(self, conversation_id: str, message: Message) -> ConversationMessage:
        return self.add_many(conversation_id, [message])[0]

    def add_many(self, conversation_id: str, messages: list[Message]) -> list[ConversationMessage]:
        with self._session_factory.begin() as session:
            if session.get(ConversationRow, conversation_id) is None:
                raise EntityNotFound(f"Không tìm thấy hội thoại '{conversation_id}'")

            last_position = session.scalar(
                select(func.max(MessageRow.position)).where(
                    MessageRow.conversation_id == conversation_id
                )
            )
            next_position = 0 if last_position is None else last_position + 1

            saved: list[ConversationMessage] = []
            for offset, message in enumerate(messages):
                entity = ConversationMessage(
                    conversation_id=conversation_id,
                    message=message,
                    position=next_position + offset,
                )
                kind, payload = encode_message(message)
                session.add(MessageRow(
                    id=entity.id,
                    conversation_id=conversation_id,
                    position=entity.position,
                    kind=kind,
                    payload=payload,
                    created_at=entity.created_at,
                ))
                saved.append(entity)
        return saved

    def list_by_conversation(self, conversation_id: str) -> list[ConversationMessage]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(MessageRow)
                .where(MessageRow.conversation_id == conversation_id)
                .order_by(MessageRow.position)
            )
            return [
                ConversationMessage(
                    id=row.id,
                    conversation_id=row.conversation_id,
                    message=decode_message(row.kind, row.payload),
                    position=row.position,
                    created_at=_as_utc(row.created_at),
                )
                for row in rows
            ]


class SqlAlchemyModelRepository(ModelRepository):
    """Triển khai ModelRepository bằng SQLAlchemy."""

    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def list_all(self) -> list[LlmModel]:
        with self._session_factory() as session:
            rows = session.scalars(select(ModelRow).order_by(ModelRow.display_name))
            return [self._to_entity(row) for row in rows]

    def get(self, model_id: str) -> LlmModel | None:
        with self._session_factory() as session:
            row = session.get(ModelRow, model_id)
            return self._to_entity(row) if row else None

    def get_by_provider_code(self, provider: str, model_code: str) -> LlmModel | None:
        with self._session_factory() as session:
            row = session.scalar(
                select(ModelRow).where(ModelRow.provider == provider, ModelRow.model_code == model_code)
            )
            return self._to_entity(row) if row else None

    def get_default(self) -> LlmModel | None:
        with self._session_factory() as session:
            row = session.scalar(select(ModelRow).where(ModelRow.is_default.is_(True)).limit(1))
            return self._to_entity(row) if row else None

    def add(self, model: LlmModel) -> LlmModel:
        try:
            with self._session_factory.begin() as session:
                session.add(self._to_row(model))
        except IntegrityError as e:
            raise EntityAlreadyExists(
                f"Model '{model.model_code}' của '{model.provider}' đã tồn tại"
            ) from e
        return model

    def update(self, model: LlmModel) -> LlmModel:
        try:
            with self._session_factory.begin() as session:
                row = session.get(ModelRow, model.id)
                if row is None:
                    raise EntityNotFound(f"Không tìm thấy model '{model.id}'")
                row.provider = model.provider
                row.display_name = model.display_name
                row.model_code = model.model_code
                row.reasoning_modes = list(model.reasoning_modes)
                row.default_reasoning = model.default_reasoning
                row.builtin_tools = list(model.builtin_tools)
                row.is_enabled = model.is_enabled
                row.is_default = model.is_default
                row.notes = model.notes
                row.last_test_at = model.last_test_at
                row.last_test_ok = model.last_test_ok
                row.last_test_report = model.last_test_report
                row.updated_at = model.updated_at
        except IntegrityError as e:
            raise EntityAlreadyExists(
                f"Model '{model.model_code}' của '{model.provider}' đã tồn tại"
            ) from e
        return model

    def delete(self, model_id: str) -> None:
        with self._session_factory.begin() as session:
            row = session.get(ModelRow, model_id)
            if row is not None:
                session.delete(row)

    def clear_default(self, except_id: str | None = None) -> None:
        with self._session_factory.begin() as session:
            query = select(ModelRow).where(ModelRow.is_default.is_(True))
            if except_id is not None:
                query = query.where(ModelRow.id != except_id)
            for row in session.scalars(query):
                row.is_default = False

    @staticmethod
    def _to_row(model: LlmModel) -> ModelRow:
        return ModelRow(
            id=model.id,
            provider=model.provider,
            display_name=model.display_name,
            model_code=model.model_code,
            reasoning_modes=list(model.reasoning_modes),
            default_reasoning=model.default_reasoning,
            builtin_tools=list(model.builtin_tools),
            is_enabled=model.is_enabled,
            is_default=model.is_default,
            notes=model.notes,
            last_test_at=model.last_test_at,
            last_test_ok=model.last_test_ok,
            last_test_report=model.last_test_report,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_entity(row: ModelRow) -> LlmModel:
        return LlmModel(
            id=row.id,
            provider=row.provider,
            display_name=row.display_name,
            model_code=row.model_code,
            reasoning_modes=list(row.reasoning_modes or []),
            default_reasoning=row.default_reasoning,
            builtin_tools=list(row.builtin_tools or []),
            is_enabled=bool(row.is_enabled),
            is_default=bool(row.is_default),
            notes=row.notes,
            last_test_at=_as_utc(row.last_test_at) if row.last_test_at else None,
            last_test_ok=row.last_test_ok,
            last_test_report=row.last_test_report,
            created_at=_as_utc(row.created_at),
            updated_at=_as_utc(row.updated_at),
        )


class SqlAlchemySessionRepository(SessionRepository):
    """Triển khai SessionRepository bằng SQLAlchemy."""

    def __init__(self, session_factory: sessionmaker[Session]):
        self._session_factory = session_factory

    def add(self, session: AuthSession) -> AuthSession:
        with self._session_factory.begin() as db:
            db.add(SessionRow(
                token=session.token,
                user_id=session.user_id,
                created_at=session.created_at,
                expires_at=session.expires_at,
            ))
        return session

    def get(self, token: str) -> AuthSession | None:
        with self._session_factory() as db:
            row = db.get(SessionRow, token)
            if row is None:
                return None
            return AuthSession(
                token=row.token,
                user_id=row.user_id,
                created_at=_as_utc(row.created_at),
                expires_at=_as_utc(row.expires_at),
            )

    def delete(self, token: str) -> None:
        with self._session_factory.begin() as db:
            row = db.get(SessionRow, token)
            if row is not None:
                db.delete(row)
