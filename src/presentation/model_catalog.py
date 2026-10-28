"""Mô hình dữ liệu và tiện ích quản lý danh mục mô hình cho UI."""

from typing import TypedDict


class ModelInfo(TypedDict):
    """Thông tin một model để hiển thị và gửi lên LLM."""
    display_name: str
    reasoning: list[str]
    default_reasoning: str | None
    builtin_tools: list[str]
    is_default: bool


# {nhà cung cấp: {tên chuẩn của model: ModelInfo}}
ModelCatalog = dict[str, dict[str, ModelInfo]]


def reasoning_modes(catalog: ModelCatalog, provider: str, model: str) -> list[str]:
    """Danh sách chế độ suy luận của model (rỗng nếu model không hỗ trợ)."""
    return catalog[provider][model]["reasoning"]


def default_reasoning(catalog: ModelCatalog, provider: str, model: str) -> str | None:
    """Chế độ suy luận mặc định của model (None nếu không hỗ trợ)."""
    info = catalog[provider][model]
    modes = info["reasoning"]
    if not modes:
        return None
    return info["default_reasoning"] if info["default_reasoning"] in modes else modes[0]


def builtin_tools(catalog: ModelCatalog, provider: str, model: str) -> list[str]:
    """Danh sách tool built-in của model (rỗng nếu model không hỗ trợ)."""
    return catalog[provider][model]["builtin_tools"]


def model_labels(catalog: ModelCatalog, provider: str) -> dict[str, str]:
    """Map {tên chuẩn: tên hiển thị} của các model thuộc một nhà cung cấp, dùng cho dropdown."""
    return {code: info["display_name"] for code, info in catalog.get(provider, {}).items()}


def default_selection(catalog: ModelCatalog) -> tuple[str, str] | None:
    """(nhà cung cấp, tên chuẩn) của model mặc định; None nếu chưa đặt mặc định hoặc catalog rỗng."""
    for provider, models in catalog.items():
        for code, info in models.items():
            if info["is_default"]:
                return provider, code
    return None
