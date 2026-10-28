"""Quản lý danh mục mô hình và kiểm tra kết nối API."""

from dataclasses import replace
from typing import Any

from src.application.model_probe import ModelProbePort
from src.application.repositories import ModelRepository, SessionRepository, UserRepository
from src.application.usecases.common import authenticate, require_admin
from src.domain.entities import LlmModel, User, utcnow
from src.domain.exceptions import EntityAlreadyExists, EntityNotFound, InvalidInput, Unauthorized

MAX_DISPLAY_NAME_LENGTH = 120
MAX_MODEL_CODE_LENGTH = 255


def _require_admin_user(sessions: SessionRepository, users: UserRepository, token: str) -> User:
    session = authenticate(sessions, token)
    user = users.get(session.user_id)
    if user is None:
        raise Unauthorized("Tài khoản không còn tồn tại, vui lòng đăng nhập lại")
    require_admin(user)
    return user


def _clean_list(values: list[str] | None) -> list[str]:
    """Bỏ khoảng trắng thừa và giá trị rỗng, giữ thứ tự, bỏ trùng. Không đổi chính tả."""
    cleaned: list[str] = []
    for value in values or []:
        item = (value or "").strip()
        if item and item not in cleaned:
            cleaned.append(item)
    return cleaned


def _check_provider(provider: str | None, supported_providers: frozenset[str]) -> str:
    provider = (provider or "").strip()
    if provider not in supported_providers:
        raise InvalidInput(
            f"Nhà cung cấp '{provider}' chưa được hỗ trợ. Chọn một trong: {', '.join(sorted(supported_providers))}"
        )
    return provider


def _check_names(display_name: str | None, model_code: str | None) -> tuple[str, str]:
    display_name = (display_name or "").strip()
    model_code = (model_code or "").strip()
    if not display_name:
        raise InvalidInput("Tên hiển thị không được để trống")
    if len(display_name) > MAX_DISPLAY_NAME_LENGTH:
        raise InvalidInput(f"Tên hiển thị tối đa {MAX_DISPLAY_NAME_LENGTH} ký tự")
    if not model_code:
        raise InvalidInput("Tên chuẩn (model_code) không được để trống")
    if len(model_code) > MAX_MODEL_CODE_LENGTH:
        raise InvalidInput(f"Tên chuẩn tối đa {MAX_MODEL_CODE_LENGTH} ký tự")
    return display_name, model_code


def _resolve_default_reasoning(modes: list[str], default: str | None) -> str | None:
    """Quy tắc chế độ mặc định: không có chế độ thì NULL; để trống thì lấy chế độ đầu tiên."""
    if not modes:
        return None
    default = (default or "").strip() or None
    if default is None:
        return modes[0]
    if default not in modes:
        raise InvalidInput(f"Chế độ mặc định '{default}' không nằm trong danh sách chế độ suy luận")
    return default


class ListModelsUseCase:
    """Liệt kê toàn bộ model (kể cả model đang tắt) cho trang quản trị."""

    def __init__(self, sessions: SessionRepository, users: UserRepository, models: ModelRepository):
        self.sessions = sessions
        self.users = users
        self.models = models

    def execute(self, token: str) -> list[LlmModel]:
        _require_admin_user(self.sessions, self.users, token)
        return self.models.list_all()


class SaveModelUseCase:
    """Thêm mới (model_id = None) hoặc sửa một model."""

    def __init__(
        self,
        sessions: SessionRepository,
        users: UserRepository,
        models: ModelRepository,
        supported_providers: frozenset[str],
    ):
        self.sessions = sessions
        self.users = users
        self.models = models
        self.supported_providers = supported_providers

    def execute(self, token: str, fields: dict[str, Any], model_id: str | None = None) -> LlmModel:
        _require_admin_user(self.sessions, self.users, token)

        provider = _check_provider(fields.get("provider"), self.supported_providers)
        display_name, model_code = _check_names(fields.get("display_name"), fields.get("model_code"))
        reasoning_modes = _clean_list(fields.get("reasoning_modes"))
        default_reasoning = _resolve_default_reasoning(reasoning_modes, fields.get("default_reasoning"))
        builtin_tools = _clean_list(fields.get("builtin_tools"))
        # Thêm mới mặc định là bật; cần nhập tường minh để tắt
        is_enabled = bool(fields.get("is_enabled", True))
        is_default = bool(fields.get("is_default", False))
        notes = (fields.get("notes") or "").strip() or None

        if is_default and not is_enabled:
            raise InvalidInput("Model mặc định phải được bật")

        duplicate = self.models.get_by_provider_code(provider, model_code)
        if duplicate is not None and duplicate.id != model_id:
            raise EntityAlreadyExists(f"Model '{model_code}' của '{provider}' đã tồn tại")

        now = utcnow()
        if model_id is None:
            model = LlmModel(
                provider=provider,
                display_name=display_name,
                model_code=model_code,
                reasoning_modes=reasoning_modes,
                default_reasoning=default_reasoning,
                builtin_tools=builtin_tools,
                is_enabled=is_enabled,
                is_default=is_default,
                notes=notes,
                created_at=now,
                updated_at=now,
            )
        else:
            existing = self.models.get(model_id)
            if existing is None:
                raise EntityNotFound(f"Không tìm thấy model '{model_id}'")
            if existing.is_default and not is_enabled:
                raise InvalidInput("Không thể tắt model đang là mặc định. Hãy đặt model khác làm mặc định trước")
            # Đổi cấu hình kỹ thuật thì kết quả Test cũ không còn đúng nữa
            config_changed = (
                provider, model_code, reasoning_modes, builtin_tools
            ) != (
                existing.provider, existing.model_code, existing.reasoning_modes, existing.builtin_tools
            )
            model = replace(
                existing,
                provider=provider,
                display_name=display_name,
                model_code=model_code,
                reasoning_modes=reasoning_modes,
                default_reasoning=default_reasoning,
                builtin_tools=builtin_tools,
                is_enabled=is_enabled,
                is_default=is_default,
                notes=notes,
                last_test_at=None if config_changed else existing.last_test_at,
                last_test_ok=None if config_changed else existing.last_test_ok,
                last_test_report=None if config_changed else existing.last_test_report,
                updated_at=now,
            )

        # Phải bỏ mặc định cũ trước khi đặt mặc định mới (ràng buộc chỉ một bản ghi mặc định)
        if is_default:
            self.models.clear_default(except_id=model.id)

        if model_id is None:
            return self.models.add(model)
        return self.models.update(model)


class DeleteModelUseCase:
    """Xóa một model. Không cho xóa model đang là mặc định."""

    def __init__(self, sessions: SessionRepository, users: UserRepository, models: ModelRepository):
        self.sessions = sessions
        self.users = users
        self.models = models

    def execute(self, token: str, model_id: str) -> None:
        _require_admin_user(self.sessions, self.users, token)
        existing = self.models.get(model_id)
        if existing is None:
            return
        if existing.is_default:
            raise InvalidInput("Không thể xóa model đang là mặc định. Hãy đặt model khác làm mặc định trước")
        self.models.delete(model_id)


class TestModelUseCase:
    """Kiểm tra model với từng chế độ suy luận bằng lời gọi API thật.

    Nhận cấu hình ứng viên nên có thể test trước khi lưu. Nếu truyền model_id của bản ghi
    có cùng nhà cung cấp và tên chuẩn thì kết quả được ghi vào last_test_*.
    """

    def __init__(
        self,
        sessions: SessionRepository,
        users: UserRepository,
        models: ModelRepository,
        probe: ModelProbePort,
        supported_providers: frozenset[str],
    ):
        self.sessions = sessions
        self.users = users
        self.models = models
        self.probe = probe
        self.supported_providers = supported_providers

    def execute(
        self,
        token: str,
        fields: dict[str, Any],
        model_id: str | None = None,
    ) -> list[dict[str, Any]]:
        _require_admin_user(self.sessions, self.users, token)

        provider = _check_provider(fields.get("provider"), self.supported_providers)
        model_code = (fields.get("model_code") or "").strip()
        if not model_code:
            raise InvalidInput("Tên chuẩn (model_code) không được để trống")
        reasoning_modes = _clean_list(fields.get("reasoning_modes"))
        builtin_tools = _clean_list(fields.get("builtin_tools"))

        # Không có chế độ suy luận thì kiểm tra đúng một lần với reasoning = None
        modes_to_test: list[str | None] = list(reasoning_modes) or [None]
        results: list[dict[str, Any]] = []
        for mode in modes_to_test:
            outcome = self.probe.probe(provider, model_code, mode, builtin_tools)
            results.append({
                "mode": mode,
                "ok": outcome.ok,
                "message": outcome.message,
                "elapsed_ms": outcome.elapsed_ms,
            })

        if model_id is not None:
            saved = self.models.get(model_id)
            if saved is not None and (saved.provider, saved.model_code) == (provider, model_code):
                self.models.update(replace(
                    saved,
                    last_test_at=utcnow(),
                    last_test_ok=all(item["ok"] for item in results),
                    last_test_report=results,
                ))
        return results
