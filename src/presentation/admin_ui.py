"""Giao diện quản trị hệ thống và cấu hình mô hình."""

from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Iterator

from fastapi.responses import RedirectResponse
from nicegui import app, run, ui

from src.domain.entities import LlmModel, User
from src.domain.exceptions import AppError, Unauthorized

if TYPE_CHECKING:
    from src.presentation.web_ui import WebUseCases

TOKEN_KEY = "token"  # Trùng với web_ui.TOKEN_KEY


@dataclass(frozen=True) 
class AdminSection:
    """Một mục trong thanh điều hướng quản trị."""
    key: str
    title: str
    path: str
    icon: str
    available: bool = True


# Thêm mục quản trị mới ở đây. Mục chưa làm (available=False) hiển thị mờ, không bấm được.
ADMIN_SECTIONS: tuple[AdminSection, ...] = (
    AdminSection("models", "Models", "/admin/models", "smart_toy"),
    AdminSection("users", "Người dùng", "/admin/users", "group", available=False),
)

FILTER_ALL, FILTER_ENABLED, FILTER_DISABLED = "all", "enabled", "disabled"


def split_csv(text: str | None) -> tuple[list[str], int]:
    """Tách chuỗi nhập theo dấu phẩy.

    Bỏ khoảng trắng thừa và phần tử rỗng, bỏ trùng, giữ nguyên chính tả và thứ tự.
    Trả về (danh sách, số mục trùng đã bỏ).
    """
    items: list[str] = []
    dropped = 0
    for raw in (text or "").split(","):
        item = raw.strip()
        if not item:
            continue
        if item in items:
            dropped += 1
            continue
        items.append(item)
    return items, dropped


def _describe_list(items: list[str], dropped: int, empty_text: str, label: str) -> str:
    """Dòng xem trước dưới ô nhập, để admin kiểm tra đã tách đúng chưa."""
    if not items:
        return empty_text
    text = f"Nhận {len(items)} {label}: " + " · ".join(items)
    if dropped:
        text += f" (đã bỏ {dropped} mục trùng)"
    return text


def _test_status(model: LlmModel) -> tuple[str, str]:
    if model.last_test_at is None:
        return "Chưa test", "grey"
    return ("Đạt", "green") if model.last_test_ok else ("Có lỗi", "red")


def _model_row(model: LlmModel) -> dict[str, Any]:
    test_label, test_color = _test_status(model)
    return {
        "id": model.id,
        "display_name": model.display_name,
        "provider": model.provider,
        "model_code": model.model_code,
        "modes": ", ".join(model.reasoning_modes) or "—",
        "is_default": "✓" if model.is_default else "",
        "status_label": "Đang bật" if model.is_enabled else "Đã tắt",
        "status_color": "green" if model.is_enabled else "grey",
        "test_label": test_label,
        "test_color": test_color,
    }


_MODEL_COLUMNS = [
    {"name": "display_name", "label": "Tên hiển thị", "field": "display_name", "align": "left", "sortable": True},
    {"name": "provider", "label": "Nhà cung cấp", "field": "provider", "align": "left", "sortable": True},
    {"name": "model_code", "label": "Tên chuẩn", "field": "model_code", "align": "left"},
    {"name": "modes", "label": "Chế độ suy luận", "field": "modes", "align": "left"},
    {"name": "is_default", "label": "Mặc định", "field": "is_default", "align": "center"},
    {"name": "status", "label": "Trạng thái", "field": "status_label", "align": "left"},
    {"name": "test", "label": "Test gần nhất", "field": "test_label", "align": "left"},
    {"name": "actions", "label": "", "field": "id", "align": "right"},
]

_STATUS_SLOT = (
    '<q-td :props="props"><q-badge outline :color="props.row.status_color" '
    ':label="props.row.status_label" /></q-td>'
)
_TEST_SLOT = (
    '<q-td :props="props"><q-badge outline :color="props.row.test_color" '
    ':label="props.row.test_label" /></q-td>'
)
_ACTIONS_SLOT = """
<q-td :props="props">
  <q-btn flat round dense icon="edit" @click="() => $parent.$emit('edit', props.row.id)">
    <q-tooltip>Sửa</q-tooltip>
  </q-btn>
  <q-btn flat round dense icon="delete_outline" color="negative"
         @click="() => $parent.$emit('delete', props.row.id)">
    <q-tooltip>Xóa</q-tooltip>
  </q-btn>
</q-td>
"""


@contextmanager
def _admin_shell(active_key: str, user: User) -> Iterator[ui.column]:
    """Khung trang quản trị: thanh điều hướng trái, thanh tiêu đề, vùng nội dung ở giữa."""
    drawer = ui.left_drawer(value=True, bordered=True).props("width=232 breakpoint=900").classes("bg-slate-50")
    with drawer:
        with ui.column().classes("w-full gap-1 p-3"):
            ui.label("Quản trị").classes(
                "text-xs font-semibold uppercase tracking-wider text-slate-500 px-2 pt-2 pb-1"
            )
            for section in ADMIN_SECTIONS:
                if section.available:
                    active = section.key == active_key
                    item_classes = "rounded-lg " + (
                        "bg-emerald-50 text-emerald-800 font-semibold border border-emerald-200/80" if active else "text-stone-700 hover:bg-stone-100"
                    )
                    with ui.item(on_click=lambda s=section: ui.navigate.to(s.path)).classes(item_classes):
                        with ui.item_section().props("avatar"):
                            ui.icon(section.icon)
                        with ui.item_section():
                            ui.item_label(section.title)
                else:
                    with ui.item().classes("rounded-lg opacity-50 cursor-not-allowed"):
                        with ui.item_section().props("avatar"):
                            ui.icon(section.icon)
                        with ui.item_section():
                            ui.item_label(section.title)
                            ui.item_label("Sắp có").props("caption")

    with ui.header(elevated=False).classes("bg-white text-stone-800 border-b border-stone-200 items-center gap-2"):
        ui.button(icon="menu", on_click=drawer.toggle).props("flat round dense").classes("text-stone-600")
        ui.icon("history_edu").classes("text-primary")
        ui.label("VNHisChat · Quản trị hệ thống").classes("font-semibold text-stone-900")
        ui.space()
        ui.label(user.display_name or user.username).classes("text-sm text-slate-500 hidden sm:block")
        ui.button("Về trang chat", icon="chat", on_click=lambda: ui.navigate.to("/")).props("flat no-caps")

    with ui.column().classes("w-full max-w-6xl mx-auto px-4 sm:px-6 py-8 gap-6") as content:
        yield content


@contextmanager
def _section_card(title: str, description: str) -> Iterator[ui.column]:
    """Khối có tiêu đề dùng để nhóm các ô trong form."""
    with ui.card().classes("w-full rounded-2xl border border-slate-200 shadow-none p-6 gap-4"):
        ui.label(title).classes("text-base font-semibold text-slate-900")
        ui.label(description).classes("text-sm text-slate-500 -mt-3")
        with ui.column().classes("w-full gap-4") as body:
            yield body


def register_admin_pages(
    usecases: "WebUseCases",
    providers: list[str],
    apply_theme: Callable[[], None],
) -> None:
    """Đăng ký các route quản trị. Gọi từ run_web_ui trước khi ui.run."""

    def guard() -> tuple[str, User] | RedirectResponse:
        """Chỉ cho phép quản trị viên đã đăng nhập; còn lại chuyển hướng."""
        token: str = app.storage.user.get(TOKEN_KEY, "")
        try:
            user = usecases.get_current_user.execute(token)
        except AppError:
            app.storage.user.pop(TOKEN_KEY, None)
            return RedirectResponse("/login")
        if not user.is_admin:
            return RedirectResponse("/")
        return token, user

    def report(exc: Exception) -> None:
        if isinstance(exc, Unauthorized):
            app.storage.user.pop(TOKEN_KEY, None)
            ui.navigate.to("/login")
        ui.notify(str(exc), type="negative", multi_line=True)

    @ui.page("/admin")
    def admin_root() -> RedirectResponse | None:
        result = guard()
        if isinstance(result, RedirectResponse):
            return result
        return RedirectResponse("/admin/models")

    # ------------------------------------------------------------------ #
    # Mục Models: danh sách
    # ------------------------------------------------------------------ #
    @ui.page("/admin/models")
    def models_page() -> RedirectResponse | None:
        result = guard()
        if isinstance(result, RedirectResponse):
            return result
        token, user = result
        apply_theme()
        content_root = ui.context.client.content
        state: dict[str, Any] = {"items": []}

        try:
            state["items"] = usecases.list_models.execute(token)
        except AppError as exc:
            report(exc)

        def visible_models() -> list[LlmModel]:
            needle = (search.value or "").strip().lower()
            status = status_filter.value
            matched = []
            for model in state["items"]:
                if status == FILTER_ENABLED and not model.is_enabled:
                    continue
                if status == FILTER_DISABLED and model.is_enabled:
                    continue
                if needle and needle not in model.display_name.lower() and needle not in model.model_code.lower():
                    continue
                matched.append(model)
            return matched

        def apply_filter() -> None:
            table.rows = [_model_row(model) for model in visible_models()]
            table.update()
            empty_hint.set_visibility(not state["items"])

        def do_delete(model_id: str, dialog: ui.dialog) -> None:
            try:
                usecases.delete_model.execute(token, model_id)
            except AppError as exc:
                report(exc)
                return
            dialog.close()
            reload()
            ui.notify("Đã xóa model", type="positive")

        def confirm_delete(model_id: str) -> None:
            model = next((m for m in state["items"] if m.id == model_id), None)
            if model is None:
                return
            with content_root, ui.dialog() as dialog, ui.card().classes("w-96 max-w-[90vw] rounded-2xl p-6 gap-3"):
                ui.label("Xóa model?").classes("text-lg font-semibold")
                ui.label(f"“{model.display_name}” sẽ bị xóa khỏi danh mục.").classes("text-slate-500")
                with ui.row().classes("w-full justify-end gap-2 mt-2"):
                    ui.button("Hủy", on_click=dialog.close).props("flat no-caps")
                    ui.button("Xóa", on_click=lambda: do_delete(model_id, dialog)).props(
                        "unelevated no-caps color=negative"
                    )
            dialog.open()

        def reload() -> None:
            try:
                state["items"] = usecases.list_models.execute(token)
            except AppError as exc:
                report(exc)
                return
            apply_filter()

        with _admin_shell("models", user) as content:
            with ui.row().classes("w-full items-end justify-between gap-4"):
                with ui.column().classes("gap-1"):
                    ui.label("Models").classes("text-2xl font-semibold text-slate-900")
                    ui.label(
                        "Danh mục model hiển thị cho người dùng khi chat. Model đang tắt sẽ không xuất hiện."
                    ).classes("text-sm text-slate-500")
                ui.button("Thêm model", icon="add", on_click=lambda: ui.navigate.to("/admin/models/new")).props(
                    "unelevated no-caps color=primary"
                )

            with ui.row().classes("w-full items-center gap-3"):
                search = ui.input(placeholder="Tìm theo tên hiển thị hoặc tên chuẩn").props(
                    "outlined dense clearable"
                ).classes("w-full sm:w-96")
                status_filter = ui.toggle(
                    {FILTER_ALL: "Tất cả", FILTER_ENABLED: "Đang bật", FILTER_DISABLED: "Đã tắt"},
                    value=FILTER_ALL,
                ).props("unelevated no-caps toggle-color=primary")

            empty_hint = ui.card().classes("w-full rounded-2xl border border-dashed border-slate-300 shadow-none p-8")
            with empty_hint:
                ui.label("Chưa có model nào").classes("text-base font-semibold text-slate-900")
                ui.label("Thêm model đầu tiên để người dùng có thể chọn khi chat.").classes("text-sm text-slate-500")
                ui.button("Thêm model", icon="add", on_click=lambda: ui.navigate.to("/admin/models/new")).props(
                    "unelevated no-caps color=primary"
                ).classes("mt-2 w-fit")

            table = ui.table(columns=_MODEL_COLUMNS, rows=[], row_key="id").classes("w-full").props(
                "flat bordered separator=horizontal"
            )
            table.add_slot("body-cell-status", _STATUS_SLOT)
            table.add_slot("body-cell-test", _TEST_SLOT)
            table.add_slot("body-cell-actions", _ACTIONS_SLOT)
            table.on("edit", lambda e: ui.navigate.to(f"/admin/models/{e.args}"))
            table.on("delete", lambda e: confirm_delete(e.args))

            search.on_value_change(apply_filter)
            status_filter.on_value_change(apply_filter)
            apply_filter()

        return None

    # ------------------------------------------------------------------ #
    # Mục Models: form thêm / sửa (trang riêng)
    # ------------------------------------------------------------------ #
    def render_model_form(model: LlmModel | None, token: str, user: User) -> None:
        apply_theme()
        model_id = model.id if model else None

        with _admin_shell("models", user) as content:
            with ui.row().classes("w-full items-center gap-2"):
                ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/admin/models")).props(
                    "flat round dense"
                )
                ui.label("Thêm model" if model is None else model.display_name).classes(
                    "text-2xl font-semibold text-slate-900"
                )

            with _section_card("Thông tin model", "Nhà cung cấp và tên định danh dùng khi gọi API."):
                with ui.element("div").classes("grid grid-cols-1 md:grid-cols-2 gap-4 w-full"):
                    provider_input = ui.select(
                        providers, label="Nhà cung cấp", value=model.provider if model else None
                    ).props("outlined")
                    display_input = ui.input(
                        "Tên hiển thị", value=model.display_name if model else ""
                    ).props("outlined")
                    code_input = ui.input(
                        "Tên chuẩn", value=model.model_code if model else ""
                    ).props("outlined")
                    ui.label(
                        "Tên chuẩn phải đúng như API yêu cầu, ví dụ gpt-5.5 hoặc sonnet."
                    ).classes("text-xs text-slate-500 md:col-span-2 -mt-2")

            with _section_card(
                "Suy luận & công cụ",
                "Nhập các giá trị cách nhau bằng dấu phẩy. Chính tả phải đúng theo nhà cung cấp.",
            ):
                initial_modes, _ = split_csv(", ".join(model.reasoning_modes) if model else "")
                modes_input = ui.input(
                    "Chế độ suy luận", value=", ".join(initial_modes), placeholder="low, medium, high"
                ).props("outlined")
                modes_hint = ui.label().classes("text-xs text-slate-500 -mt-2")
                default_input = ui.select(
                    initial_modes,
                    label="Chế độ mặc định",
                    clearable=True,
                    value=model.default_reasoning if model else None,
                ).props("outlined").classes("md:w-1/2")
                ui.label("Để trống thì dùng chế độ đầu tiên trong danh sách.").classes(
                    "text-xs text-slate-500 -mt-2"
                )

                tools_input = ui.input(
                    "Tool built-in",
                    value=", ".join(model.builtin_tools) if model else "",
                    placeholder="web_search, code_interpreter",
                ).props("outlined")
                tools_hint = ui.label().classes("text-xs text-slate-500 -mt-2")

            with _section_card("Trạng thái", "Quyết định model có được dùng và có được chọn sẵn hay không."):
                enabled_input = ui.switch(
                    "Bật model (người dùng có thể chọn)", value=model.is_enabled if model else True
                )
                default_switch = ui.switch(
                    "Mặc định cho người dùng mới", value=model.is_default if model else False
                )

            with _section_card("Ghi chú", "Nguồn đã đối chiếu, ngày kiểm tra, lưu ý khi dùng."):
                notes_input = ui.textarea(value=(model.notes or "") if model else "").props(
                    "outlined autogrow"
                ).classes("w-full")

            with _section_card(
                "Kiểm tra model",
                "Gọi thử model với từng chế độ suy luận. Kiểm tra cả khi chưa lưu.",
            ):
                test_box = ui.column().classes("w-full gap-2")
                ui.button("Chạy kiểm tra", icon="science", on_click=lambda: run_test()).props(
                    "outline no-caps"
                ).classes("w-fit")

            def refresh_hints() -> None:
                modes, modes_dropped = split_csv(modes_input.value)
                tools, tools_dropped = split_csv(tools_input.value)
                modes_hint.text = _describe_list(modes, modes_dropped, "Không có chế độ suy luận.", "chế độ")
                tools_hint.text = _describe_list(tools, tools_dropped, "Không có tool built-in.", "tool")
                current = default_input.value
                default_input.set_options(modes, value=current if current in modes else None)
                default_input.set_enabled(bool(modes))

            def current_fields() -> dict[str, Any]:
                modes, _ = split_csv(modes_input.value)
                tools, _ = split_csv(tools_input.value)
                return {
                    "provider": provider_input.value,
                    "display_name": display_input.value,
                    "model_code": code_input.value,
                    "reasoning_modes": modes,
                    "default_reasoning": default_input.value if modes else None,
                    "builtin_tools": tools,
                    "is_enabled": enabled_input.value,
                    "is_default": default_switch.value,
                    "notes": notes_input.value,
                }

            async def run_test() -> None:
                test_box.clear()
                with test_box:
                    ui.label("Đang kiểm tra...").classes("text-sm text-slate-500")
                try:
                    results = await run.io_bound(
                        usecases.test_model.execute, token, current_fields(), model_id
                    )
                except AppError as exc:
                    test_box.clear()
                    with test_box:
                        ui.label(str(exc)).classes("text-sm text-red-600")
                    return
                test_box.clear()
                with test_box:
                    for item in results:
                        label = item["mode"] or "không có chế độ suy luận"
                        with ui.row().classes("items-start no-wrap gap-2"):
                            ui.icon(
                                "check_circle" if item["ok"] else "error", size="18px"
                            ).classes("text-green-600" if item["ok"] else "text-red-600")
                            with ui.column().classes("gap-0 min-w-0"):
                                ui.label(f"{label} · {item['elapsed_ms']} ms").classes("text-sm font-medium")
                                if not item["ok"]:
                                    ui.label(item["message"]).classes("text-xs text-red-600 break-all")

            def save() -> None:
                try:
                    usecases.save_model.execute(token, current_fields(), model_id)
                except AppError as exc:
                    report(exc)
                    return
                ui.notify("Đã lưu model", type="positive")
                ui.navigate.to("/admin/models")

            modes_input.on_value_change(refresh_hints)
            tools_input.on_value_change(refresh_hints)
            refresh_hints()

            with ui.row().classes(
                "w-full justify-end gap-2 sticky bottom-0 bg-white/95 py-3 border-t border-slate-200"
            ):
                ui.button("Hủy", on_click=lambda: ui.navigate.to("/admin/models")).props("flat no-caps")
                ui.button("Lưu", icon="save", on_click=save).props("unelevated no-caps color=primary")

    @ui.page("/admin/models/new")
    def model_new_page() -> RedirectResponse | None:
        result = guard()
        if isinstance(result, RedirectResponse):
            return result
        token, user = result
        render_model_form(None, token, user)
        return None

    @ui.page("/admin/models/{model_id}")
    def model_edit_page(model_id: str) -> RedirectResponse | None:
        result = guard()
        if isinstance(result, RedirectResponse):
            return result
        token, user = result
        try:
            model = next((m for m in usecases.list_models.execute(token) if m.id == model_id), None)
        except AppError as exc:
            report(exc)
            return RedirectResponse("/admin/models")
        if model is None:
            ui.notify("Không tìm thấy model này", type="negative")
            return RedirectResponse("/admin/models")
        render_model_form(model, token, user)
        return None
