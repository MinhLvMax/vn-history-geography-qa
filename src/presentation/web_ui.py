"""Giao diện web VNHisChat xây dựng bằng NiceGUI."""

import asyncio
import concurrent.futures
from dataclasses import dataclass
from typing import Any, Callable

from fastapi.responses import RedirectResponse
from nicegui import app, run, ui

from src.application.approval import ApprovalPort
from src.presentation.admin_ui import register_admin_pages
from src.application.usecases import (
    CreateConversationUseCase,
    DeleteConversationUseCase,
    GetConversationMessagesUseCase,
    GetCurrentUserUseCase,
    DeleteModelUseCase,
    GetUiStateUseCase,
    ListConversationsUseCase,
    ListModelsUseCase,
    LoginUseCase,
    LogoutUseCase,
    RegisterUseCase,
    RenameConversationUseCase,
    SaveModelUseCase,
    SaveUiStateUseCase,
    SendMessageUseCase,
    TestModelUseCase,
)
from src.domain.entities import Conversation
from src.domain.exceptions import AppError, Unauthorized
from src.domain.models import (
    AssistantMessage,
    Message,
    TextPart,
    ToolCallMessage,
    ToolResultMessage,
    UserMessage,
    parts_to_text,
)
from src.presentation.model_catalog import (
    ModelCatalog,
    builtin_tools,
    default_reasoning,
    default_selection,
    model_labels,
    reasoning_modes,
)

APP_NAME = "VNHisChat"
PRIMARY_COLOR = "#2d6a4f"     # Xanh lá cây tre
SECONDARY_COLOR = "#6c4a35"   # Nâu đất
TITLE_MAX_LENGTH = 48
TOKEN_KEY = "token"

SUGGESTIONS = [
    "Trận Bạch Đằng năm 938 của Ngô Quyền diễn ra như thế nào và có ý nghĩa lịch sử gì?",
    "Vương triều nhà Lý dời đô về Thăng Long vào năm nào và vì sao?",
    "Chiến dịch Điện Biên Phủ năm 1954 kéo dài bao nhiêu ngày và chia làm mấy đợt?",
    "Quá trình xác lập và thực thi chủ quyền đối với quần đảo Hoàng Sa, Trường Sa qua các thời kỳ?",
]

TOOL_METADATA = {
    "rag_search_chunks": {
        "label": "Tra cứu tư liệu văn bản (Vector)",
        "icon": "travel_explore",
    },
    "rag_search_graph": {
        "label": "Khai phá đồ thị tri thức (Graph)",
        "icon": "hub",
    },
    "rag_read_chunks": {
        "label": "Đọc trang sách gốc",
        "icon": "menu_book",
    },
}

_HEAD_HTML = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  body { font-family: 'Inter', system-ui, sans-serif; background: #f7f9f6; color: #1c1917; }
  .nicegui-content { padding: 0 !important; }
  .chat-markdown p { margin: 0 0 .6rem 0; }
  .chat-markdown p:last-child { margin-bottom: 0; }
  .chat-markdown pre { background: #1c2820; color: #e2e8f0; padding: .75rem 1rem;
                       border-radius: .6rem; overflow-x: auto; font-size: .85rem; }
  .chat-markdown code {
    background: #eef2ed;
    color: #2d6a4f;
    padding: 0.15rem 0.35rem;
    border-radius: 0.3rem;
    font-size: 0.88em;
    font-weight: 500;
  }
  /* Cuộc trò chuyện & nút 3 chấm */
  .conv-item {
    width: 100% !important;
    max-width: 100% !important;
    box-sizing: border-box !important;
    position: relative !important;
    overflow: hidden !important;
  }
  .conv-item .conv-menu {
    opacity: 0;
    transition: opacity .15s ease;
    flex-shrink: 0 !important;
    margin-left: auto !important;
  }
  .conv-item:hover .conv-menu,
  .conv-item.active .conv-menu {
    opacity: 1 !important;
  }
  .conv-title-wrap {
    flex: 1 1 0% !important;
    min-width: 0 !important;
    max-width: 100% !important;
    overflow: hidden !important;
  }

  /* Khung cuộn thanh bên - thuần CSS tự động co giãn 100% không bị kẹt kích thước */
  .sidebar-scroll {
    overflow-y: auto !important;
    overflow-x: hidden !important;
    width: 100% !important;
    max-width: 100% !important;
    min-width: 0 !important;
    box-sizing: border-box !important;
  }
  .sidebar-scroll::-webkit-scrollbar {
    width: 4px;
  }
  .sidebar-scroll::-webkit-scrollbar-track {
    background: transparent;
  }
  .sidebar-scroll::-webkit-scrollbar-thumb {
    background: rgba(255, 255, 255, 0.15);
    border-radius: 4px;
  }
  .sidebar-scroll::-webkit-scrollbar-thumb:hover {
    background: rgba(255, 255, 255, 0.3);
  }

  /* Đảm bảo nội dung Quasar drawer co giãn 100% */
  .q-drawer--left, .q-drawer--left .q-drawer__content {
    box-sizing: border-box !important;
    overflow-x: hidden !important;
  }
  .typing span { width: 7px; height: 7px; border-radius: 9999px; background: #2d6a4f;
                 display: inline-block; animation: blink 1.2s infinite both; }
  .typing span:nth-child(2) { animation-delay: .2s; }
  .typing span:nth-child(3) { animation-delay: .4s; }
  @keyframes blink { 0%, 80%, 100% { opacity: .25; } 40% { opacity: 1; } }

  /* Thanh kéo chỉnh độ rộng thanh bên (Sidebar Resizer) */
  .sidebar-resizer {
    position: absolute;
    top: 0;
    right: 0;
    width: 8px;
    height: 100%;
    cursor: col-resize;
    z-index: 50;
    touch-action: none;
    user-select: none;
  }
  .sidebar-resizer::after {
    content: '';
    position: absolute;
    top: 0;
    right: 0;
    width: 2px;
    height: 100%;
    background-color: rgba(255, 255, 255, 0.08);
    transition: background-color .2s ease, width .2s ease;
  }
  .sidebar-resizer:hover::after,
  .sidebar-resizer.is-resizing::after {
    width: 3px;
    background-color: #52b788;
    box-shadow: 0 0 8px rgba(82, 183, 136, 0.6);
  }
  body.resizing-sidebar {
    user-select: none !important;
    cursor: col-resize !important;
  }
  body.resizing-sidebar * {
    user-select: none !important;
    cursor: col-resize !important;
  }
</style>
<script>
(function() {
  const MIN_WIDTH = 190;
  const DEFAULT_WIDTH = 265; // ~7 cm theo chuẩn màn hình 96 DPI (7 * 96 / 2.54 = 264.57px)
  const STORAGE_KEY = 'agentv2_sidebar_width_v2';

  function getMaxWidth() {
    return Math.min(700, Math.round(window.innerWidth * 0.7));
  }

  function applySidebarWidth(width) {
    const drawer = document.querySelector('.q-drawer--left');
    if (drawer) {
      drawer.style.width = width + 'px';
    }
    const container = document.querySelector('.q-page-container');
    if (container && drawer && drawer.classList.contains('q-drawer--standard')) {
      container.style.paddingLeft = width + 'px';
    }
  }

  function initSidebarResizer() {
    const resizer = document.getElementById('sidebar-resizer');
    const drawer = document.querySelector('.q-drawer--left');
    if (!resizer || !drawer || resizer.dataset.initialized === 'true') {
      return false;
    }
    resizer.dataset.initialized = 'true';

    let saved = localStorage.getItem(STORAGE_KEY);
    let initialWidth = saved ? parseInt(saved, 10) : DEFAULT_WIDTH;
    if (isNaN(initialWidth) || initialWidth < MIN_WIDTH) {
      initialWidth = DEFAULT_WIDTH;
    }
    const maxW = getMaxWidth();
    if (initialWidth > maxW) initialWidth = maxW;

    applySidebarWidth(initialWidth);
    if (typeof emitEvent === 'function') {
      emitEvent('sidebar_resized', { width: initialWidth });
    }

    let isDragging = false;
    let startX = 0;
    let startWidth = 0;

    function startDrag(clientX) {
      isDragging = true;
      startX = clientX;
      startWidth = drawer.getBoundingClientRect().width;
      resizer.classList.add('is-resizing');
      document.body.classList.add('resizing-sidebar');
    }

    function doDrag(clientX) {
      if (!isDragging) return;
      const delta = clientX - startX;
      let newWidth = Math.round(startWidth + delta);
      if (newWidth < MIN_WIDTH) newWidth = MIN_WIDTH;
      const currentMax = getMaxWidth();
      if (newWidth > currentMax) newWidth = currentMax;
      applySidebarWidth(newWidth);
    }

    function stopDrag() {
      if (!isDragging) return;
      isDragging = false;
      resizer.classList.remove('is-resizing');
      document.body.classList.remove('resizing-sidebar');

      const finalWidth = Math.round(drawer.getBoundingClientRect().width);
      if (!isNaN(finalWidth) && finalWidth >= MIN_WIDTH) {
        localStorage.setItem(STORAGE_KEY, finalWidth);
        if (typeof emitEvent === 'function') {
          emitEvent('sidebar_resized', { width: finalWidth });
        }
      }
    }

    resizer.addEventListener('mousedown', function(e) {
      if (e.button !== 0) return;
      startDrag(e.clientX);
      e.preventDefault();
    });

    window.addEventListener('mousemove', function(e) {
      if (isDragging) {
        doDrag(e.clientX);
      }
    });

    window.addEventListener('mouseup', function() {
      if (isDragging) {
        stopDrag();
      }
    });

    resizer.addEventListener('touchstart', function(e) {
      if (e.touches.length === 1) {
        startDrag(e.touches[0].clientX);
      }
    }, { passive: true });

    window.addEventListener('touchmove', function(e) {
      if (isDragging && e.touches.length === 1) {
        doDrag(e.touches[0].clientX);
      }
    }, { passive: true });

    window.addEventListener('touchend', function() {
      if (isDragging) {
        stopDrag();
      }
    });

    window.addEventListener('resize', function() {
      const currentW = drawer.getBoundingClientRect().width;
      if (currentW >= MIN_WIDTH) {
        applySidebarWidth(currentW);
      }
    });

    return true;
  }

  function setup() {
    if (!initSidebarResizer()) {
      const observer = new MutationObserver(function() {
        if (initSidebarResizer()) {
          observer.disconnect();
        }
      });
      observer.observe(document.documentElement, { childList: true, subtree: true });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setup);
  } else {
    setup();
  }
})();
</script>
"""


@dataclass
class WebUseCases:
    """Các use case mà giao diện web sử dụng (Bootstrap khởi tạo và tiêm vào)."""
    register: RegisterUseCase
    login: LoginUseCase
    logout: LogoutUseCase
    get_current_user: GetCurrentUserUseCase
    get_ui_state: GetUiStateUseCase
    save_ui_state: SaveUiStateUseCase
    list_conversations: ListConversationsUseCase
    get_conversation_messages: GetConversationMessagesUseCase
    create_conversation: CreateConversationUseCase
    rename_conversation: RenameConversationUseCase
    delete_conversation: DeleteConversationUseCase
    send_message: SendMessageUseCase
    list_models: ListModelsUseCase
    save_model: SaveModelUseCase
    delete_model: DeleteModelUseCase
    test_model: TestModelUseCase


def _apply_theme() -> None:
    ui.add_head_html(_HEAD_HTML)
    ui.colors(primary=PRIMARY_COLOR, secondary=SECONDARY_COLOR)


class WebApprover(ApprovalPort):
    """Xin xác nhận của người dùng bằng hộp thoại trên đúng tab trình duyệt đang chat.

    Agent chạy trong luồng nền (run.io_bound) nên confirm() được phép chặn: nó gửi yêu cầu mở hộp thoại
    sang vòng sự kiện của NiceGUI rồi chờ người dùng trả lời. Quá thời gian thì coi như từ chối.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, page_root: ui.element, timeout_seconds: float = 300):
        self.loop = loop
        self.page_root = page_root
        self.timeout_seconds = timeout_seconds

    def confirm(self, title: str, details: str) -> bool:
        future = asyncio.run_coroutine_threadsafe(self._ask(title, details), self.loop)
        try:
            return future.result(timeout=self.timeout_seconds)
        except concurrent.futures.TimeoutError:
            future.cancel()
            return False

    async def _ask(self, title: str, details: str) -> bool:
        with self.page_root, ui.dialog().props("persistent") as dialog, ui.card().classes(
            "w-[36rem] max-w-full rounded-2xl p-6 gap-4"
        ):
            with ui.row().classes("items-center gap-3 no-wrap"):
                with ui.element("div").classes(
                    "w-10 h-10 shrink-0 rounded-full bg-amber-100 flex items-center justify-center"
                ):
                    ui.icon("shield", size="22px").classes("text-amber-700")
                ui.label(title).classes("text-lg font-semibold text-stone-900")
            ui.label(
                "Yêu cầu xác nhận từ trợ lý VNHisChat. "
                "Chỉ cho phép nếu bạn đồng ý thực hiện thao tác này."
            ).classes("text-sm text-stone-600")
            ui.label(details).classes(
                "w-full text-xs font-mono whitespace-pre-wrap bg-stone-50 border border-stone-200 "
                "rounded-lg p-3 max-h-64 overflow-auto text-stone-700"
            )
            with ui.row().classes("w-full justify-end gap-2"):
                ui.button("Từ chối", on_click=lambda: dialog.submit(False)).props("flat no-caps")
                ui.button("Cho phép", on_click=lambda: dialog.submit(True)).props(
                    "unelevated no-caps color=primary"
                )
        try:
            return bool(await dialog)
        finally:
            dialog.delete()


def _tool_info(tool_name: str) -> tuple[str, str]:
    """Lấy tên hiển thị tiếng Việt và biểu tượng cho tool RAG."""
    meta = TOOL_METADATA.get(tool_name, {"label": tool_name, "icon": "build"})
    return meta["label"], meta["icon"]


def _describe_tool_call(tool_call: ToolCallMessage.ToolCall) -> tuple[str, str]:
    """Nhãn ngắn gọn và icon cho một lần gọi tool RAG để người dùng theo dõi."""
    friendly_name, icon = _tool_info(tool_call.name)
    main_arg = next(
        (
            tool_call.kwargs[key]
            for key in ("query", "entities", "chunk_ids", "path", "root", "file_path")
            if tool_call.kwargs.get(key)
        ),
        None,
    )
    if isinstance(main_arg, list):
        main_arg = ", ".join(str(x) for x in main_arg[:3]) + ("…" if len(main_arg) > 3 else "")
    elif main_arg is not None:
        main_arg = str(main_arg)

    if tool_call.kwargs.get("query") and main_arg != tool_call.kwargs["query"]:
        main_arg = f"{main_arg} · “{tool_call.kwargs['query']}”"

    label = f"{friendly_name} · {main_arg}" if main_arg else friendly_name
    trimmed = label if len(label) <= 90 else label[:89] + "…"
    return trimmed, icon


def _make_title(text: str) -> str:
    """Tạo tiêu đề hội thoại từ tin nhắn đầu tiên."""
    title = " ".join(text.split())
    return title if len(title) <= TITLE_MAX_LENGTH else title[: TITLE_MAX_LENGTH - 1] + "…"


def run_web_ui(
    usecases: WebUseCases,
    model_catalog: Callable[[], ModelCatalog],
    providers: list[str],
    storage_secret: str,
    **ui_run_kwargs: Any,
) -> None:
    """Khởi chạy giao diện web NiceGUI.

    Các phụ thuộc (usecases, model_catalog, providers, storage_secret) được tiêm từ Bootstrap,
    tầng Presentation chỉ lo hiển thị và nhận thao tác của người dùng.
    model_catalog là hàm nạp lại danh mục mỗi lần mở trang, để thay đổi của quản trị viên có hiệu lực ngay.
    """

    # ------------------------------------------------------------------ #
    # Trang đăng nhập / đăng ký
    # ------------------------------------------------------------------ #
    @ui.page("/login")
    def login_page() -> RedirectResponse | None:
        token = app.storage.user.get(TOKEN_KEY)
        if token:
            try:
                usecases.get_current_user.execute(token)
                return RedirectResponse("/")
            except AppError:
                app.storage.user.pop(TOKEN_KEY, None)
        _apply_theme()

        def finish_login(username: str, password: str) -> None:
            session = usecases.login.execute(username, password)
            app.storage.user[TOKEN_KEY] = session.token
            ui.navigate.to("/")

        def do_login() -> None:
            try:
                finish_login(login_username.value, login_password.value)
            except AppError as exc:
                ui.notify(str(exc), type="negative")

        def do_register() -> None:
            if reg_password.value != reg_confirm.value:
                ui.notify("Mật khẩu nhập lại không khớp", type="negative")
                return
            try:
                usecases.register.execute(
                    reg_username.value, reg_password.value, (reg_display.value or "").strip() or None
                )
                finish_login(reg_username.value, reg_password.value)
            except AppError as exc:
                ui.notify(str(exc), type="negative")

        with ui.element("div").classes(
            "min-h-screen w-full flex items-center justify-center "
            "bg-gradient-to-br from-emerald-50 via-stone-50 to-amber-50/40 p-4"
        ):
            with ui.column().classes("w-full max-w-md items-center gap-6"):
                with ui.column().classes("items-center gap-2 text-center"):
                    with ui.element("div").classes(
                        "w-16 h-16 rounded-2xl bg-primary flex items-center justify-center shadow-lg shadow-emerald-900/10"
                    ):
                        ui.icon("history_edu", size="34px").classes("text-white")
                    ui.label(APP_NAME).classes("text-3xl font-extrabold text-stone-900 tracking-tight")
                    ui.label("Trợ lý Hỏi đáp Lịch sử & Địa lý Việt Nam").classes("text-stone-600 font-medium")
                    with ui.element("div").classes(
                        "text-xs text-emerald-800 bg-emerald-100/70 border border-emerald-200/80 px-3 py-1 rounded-full font-medium mt-1"
                    ):
                        ui.label("Bộ 15 tập Lịch sử Việt Nam (Viện Sử học 2017)")

                with ui.card().classes("w-full p-0 rounded-2xl shadow-xl border border-stone-200/80 bg-white"):
                    with ui.tabs().classes("w-full text-stone-600").props(
                        "active-color=primary indicator-color=primary align=justify narrow-indicator"
                    ) as tabs:
                        login_tab = ui.tab("Đăng nhập")
                        register_tab = ui.tab("Đăng ký")
                    ui.separator()
                    with ui.tab_panels(tabs, value=login_tab).classes("w-full").props("animated"):
                        with ui.tab_panel(login_tab).classes("p-6"):
                            with ui.column().classes("w-full gap-4"):
                                login_username = ui.input("Tên đăng nhập").props(
                                    "outlined autofocus"
                                ).classes("w-full")
                                login_password = ui.input(
                                    "Mật khẩu", password=True, password_toggle_button=True
                                ).props("outlined").classes("w-full").on("keydown.enter", do_login)
                                ui.button("Đăng nhập", on_click=do_login).props(
                                    "unelevated size=lg no-caps color=primary"
                                ).classes("w-full rounded-xl")

                        with ui.tab_panel(register_tab).classes("p-6"):
                            with ui.column().classes("w-full gap-4"):
                                reg_display = ui.input("Tên hiển thị (không bắt buộc)").props(
                                    "outlined"
                                ).classes("w-full")
                                reg_username = ui.input("Tên đăng nhập").props("outlined").classes("w-full")
                                reg_password = ui.input(
                                    "Mật khẩu (tối thiểu 6 ký tự)", password=True, password_toggle_button=True
                                ).props("outlined").classes("w-full")
                                reg_confirm = ui.input(
                                    "Nhập lại mật khẩu", password=True
                                ).props("outlined").classes("w-full").on("keydown.enter", do_register)
                                ui.button("Tạo tài khoản", on_click=do_register).props(
                                    "unelevated size=lg no-caps color=primary"
                                ).classes("w-full rounded-xl")

    # ------------------------------------------------------------------ #
    # Trang chat
    # ------------------------------------------------------------------ #
    @ui.page("/")
    def chat_page(c: str | None = None) -> RedirectResponse | None:
        token: str = app.storage.user.get(TOKEN_KEY, "")
        try:
            user = usecases.get_current_user.execute(token)
        except AppError:
            app.storage.user.pop(TOKEN_KEY, None)
            return RedirectResponse("/login")

        _apply_theme()
        # Nạp lại danh mục model mỗi lần mở trang để thay đổi của quản trị viên có hiệu lực ngay
        catalog: ModelCatalog = model_catalog()
        # Hộp thoại phải gắn vào cấp trang, không gắn vào menu (menu đóng sẽ ẩn luôn hộp thoại)
        page_root = ui.context.client.content
        state: dict[str, Any] = {
            "conversation_id": None,
            "conversations": [],
            "messages": [],
            "pending_text": None,
            "restoring": False,  # Đang áp lại lựa chọn đã lưu thì không ghi ngược lên CSDL
        }

        # Nạp dữ liệu ban đầu trước khi dựng giao diện để lần hiển thị đầu tiên đã có dữ liệu
        initial_error: AppError | None = None
        saved_ui: dict[str, Any] = {}
        try:
            state["conversations"] = usecases.list_conversations.execute(token)
            saved_ui = usecases.get_ui_state.execute(token)
            # Ưu tiên hội thoại trên URL; không có thì dùng hội thoại đã mở lần trước (nếu còn tồn tại)
            saved_id = saved_ui.get("conversation_id")
            if not c and saved_id not in {conversation.id for conversation in state["conversations"]}:
                saved_id = None
            conversation_id = c or saved_id
            if conversation_id:
                state["messages"] = usecases.get_conversation_messages.execute(token, conversation_id)
                state["conversation_id"] = conversation_id
        except AppError as exc:
            initial_error = exc

        def handle_error(exc: Exception) -> None:
            """Phiên hết hạn thì về trang đăng nhập, lỗi khác thì báo cho người dùng."""
            if isinstance(exc, Unauthorized):
                app.storage.user.pop(TOKEN_KEY, None)
                ui.navigate.to("/login")
            ui.notify(str(exc), type="negative", multi_line=True)

        def guarded(action: Callable[[], None]) -> None:
            try:
                action()
            except AppError as exc:
                handle_error(exc)

        # ---------------- Dữ liệu ----------------
        def load_conversations() -> None:
            state["conversations"] = usecases.list_conversations.execute(token)
            conversation_list.refresh()

        def persist_ui_state() -> None:
            """Lưu hội thoại và lựa chọn model hiện tại để lần đăng nhập sau khôi phục."""
            if state["restoring"]:
                return
            try:
                usecases.save_ui_state.execute(token, {
                    "conversation_id": state["conversation_id"],
                    "provider": provider_select.value,
                    "model": model_select.value,
                    "reasoning": reasoning_select.value,
                    "builtin_enabled": bool(builtin_switch.value),
                    "builtin_tools": list(builtin_select.value or []),
                })
            except AppError:
                pass  # Lưu trạng thái giao diện là việc phụ, không để lỗi này làm gián đoạn chat

        def restore_ui_state(saved: dict[str, Any]) -> None:
            """Áp lại lựa chọn đã lưu theo thứ tự provider → model → suy luận → tool built-in.

            Giá trị không còn hợp lệ (vd. model đã bị gỡ khỏi catalog) thì giữ mặc định.
            """
            state["restoring"] = True
            try:
                if not catalog:
                    return
                provider = saved.get("provider")
                if provider not in catalog:
                    provider = (default_selection(catalog) or (list(catalog)[0], None))[0]
                provider_select.value = provider
                if saved.get("model") in catalog[provider]:
                    model_select.value = saved["model"]

                provider, model = provider_select.value, model_select.value
                if saved.get("reasoning") in reasoning_modes(catalog, provider, model):
                    reasoning_select.value = saved["reasoning"]

                tools_of_model = builtin_tools(catalog, provider, model)
                if tools_of_model:
                    builtin_select.value = [t for t in saved.get("builtin_tools", []) if t in tools_of_model]
                    builtin_switch.value = bool(saved.get("builtin_enabled", True))
            finally:
                state["restoring"] = False

        def open_conversation(conversation_id: str | None) -> None:
            state["conversation_id"] = conversation_id
            state["messages"] = (
                usecases.get_conversation_messages.execute(token, conversation_id)
                if conversation_id else []
            )
            # Ghi hội thoại đang mở lên URL để tải lại trang (F5) vẫn giữ nguyên
            ui.navigate.history.replace(f"/?c={conversation_id}" if conversation_id else "/")
            persist_ui_state()
            conversation_list.refresh()
            chat_view.refresh()
            scroll_to_bottom()
            message_input.run_method("focus")

        def current_title() -> str:
            for conversation in state["conversations"]:
                if conversation.id == state["conversation_id"]:
                    return conversation.title
            return "Cuộc trò chuyện mới"

        # ---------------- Hộp thoại đổi tên / xóa ----------------
        async def rename_dialog(conversation: Conversation) -> None:
            with page_root, ui.dialog() as dialog, ui.card().classes("w-96 max-w-[90vw] rounded-2xl p-6 gap-4"):
                ui.label("Đổi tên cuộc trò chuyện").classes("text-lg font-semibold")
                title_input = ui.input("Tiêu đề", value=conversation.title).props(
                    "outlined autofocus"
                ).classes("w-full").on("keydown.enter", lambda: dialog.submit(title_input.value))
                with ui.row().classes("w-full justify-end gap-2"):
                    ui.button("Hủy", on_click=lambda: dialog.submit(None)).props("flat no-caps")
                    ui.button("Lưu", on_click=lambda: dialog.submit(title_input.value)).props(
                        "unelevated no-caps"
                    )
            new_title = await dialog
            if new_title is None:
                return

            def apply() -> None:
                usecases.rename_conversation.execute(token, conversation.id, new_title)
                load_conversations()
                chat_header.refresh()
                ui.notify("Đã đổi tên cuộc trò chuyện", type="positive")

            guarded(apply)

        async def delete_dialog(conversation: Conversation) -> None:
            with page_root, ui.dialog() as dialog, ui.card().classes("w-96 max-w-[90vw] rounded-2xl p-6 gap-3"):
                ui.label("Xóa cuộc trò chuyện?").classes("text-lg font-semibold")
                ui.label(f"“{conversation.title}” và toàn bộ tin nhắn sẽ bị xóa vĩnh viễn.").classes(
                    "text-slate-500"
                )
                with ui.row().classes("w-full justify-end gap-2 mt-2"):
                    ui.button("Hủy", on_click=lambda: dialog.submit(False)).props("flat no-caps")
                    ui.button("Xóa", on_click=lambda: dialog.submit(True)).props(
                        "unelevated no-caps color=negative"
                    )
            if not await dialog:
                return

            def apply() -> None:
                usecases.delete_conversation.execute(token, conversation.id)
                load_conversations()
                if state["conversation_id"] == conversation.id:
                    open_conversation(None)
                    chat_header.refresh()
                ui.notify("Đã xóa cuộc trò chuyện", type="positive")

            guarded(apply)

        def logout() -> None:
            usecases.logout.execute(token)
            app.storage.user.pop(TOKEN_KEY, None)
            ui.navigate.to("/login")


        # ---------------- Sidebar ----------------
        @ui.refreshable
        def conversation_list() -> None:
            if not state["conversations"]:
                ui.label("Chưa có cuộc trò chuyện nào").classes("text-sm text-stone-400 px-3 py-2")
                return
            for conversation in state["conversations"]:
                active = conversation.id == state["conversation_id"]
                with ui.row().classes(
                    "conv-item group w-full items-center no-wrap gap-1 rounded-lg px-2 py-1 cursor-pointer relative "
                    + ("active bg-emerald-900/60 text-white font-medium border border-emerald-700/40" if active else "text-stone-300 hover:bg-white/5")
                ):
                    with ui.row().classes("conv-title-wrap items-center no-wrap gap-2 cursor-pointer py-1").on(
                        "click",
                        lambda c=conversation: guarded(lambda: (open_conversation(c.id), chat_header.refresh())),
                    ):
                        ui.icon("chat_bubble_outline", size="16px").classes(
                            "text-emerald-400 shrink-0 select-none" if active else "text-stone-400 shrink-0 select-none"
                        )
                        ui.label(conversation.title).classes(
                            "flex-1 min-w-0 truncate text-sm select-none"
                        ).tooltip(conversation.title)

                    with ui.button(icon="more_horiz").props("flat round dense size=sm").classes(
                        "conv-menu shrink-0 text-stone-400 hover:text-white"
                    ):
                        ui.tooltip("Tùy chọn")
                        with ui.menu().props("auto-close"):
                            with ui.menu_item(on_click=lambda c=conversation: rename_dialog(c)):
                                with ui.row().classes("items-center gap-3 no-wrap"):
                                    ui.icon("edit", size="18px")
                                    ui.label("Đổi tên")
                            with ui.menu_item(on_click=lambda c=conversation: delete_dialog(c)):
                                with ui.row().classes("items-center gap-3 no-wrap text-red-600"):
                                    ui.icon("delete_outline", size="18px")
                                    ui.label("Xóa")

        with ui.left_drawer(value=True, fixed=True).props("width=265 breakpoint=900").classes(
            "bg-[#1c2820] p-0 relative text-stone-200"
        ) as drawer:
            ui.element("div").classes("sidebar-resizer").props(
                'id="sidebar-resizer" title="Kéo để thay đổi độ rộng thanh bên"'
            )
            with ui.column().classes("w-full h-full no-wrap gap-0"):
                with ui.row().classes("items-center gap-3 px-4 pt-5 pb-4 no-wrap"):
                    with ui.element("div").classes(
                        "w-9 h-9 rounded-xl bg-primary flex items-center justify-center shadow-sm"
                    ):
                        ui.icon("history_edu", size="20px").classes("text-white")
                    with ui.column().classes("gap-0"):
                        ui.label(APP_NAME).classes("text-lg font-bold text-white tracking-wide")
                        ui.label("Lịch sử & Địa lý VN").classes("text-[10px] text-emerald-200/80 -mt-1")

                ui.button(
                    "Cuộc trò chuyện mới",
                    icon="add",
                    on_click=lambda: (open_conversation(None), chat_header.refresh()),
                ).props("unelevated no-caps align=left").classes(
                    "mx-3 rounded-xl bg-emerald-800/40 text-emerald-100 hover:bg-emerald-800/70 border border-emerald-700/30"
                ).style("width: calc(100% - 1.5rem)")

                ui.label("Gần đây").classes(
                    "text-xs font-semibold uppercase tracking-wider text-emerald-300/50 px-4 pt-5 pb-2 shrink-0"
                )
                with ui.column().classes("flex-grow w-full sidebar-scroll px-2 gap-0.5 no-wrap"):
                    conversation_list()

                ui.separator().classes("bg-emerald-900/40")
                with ui.row().classes("w-full items-center no-wrap gap-3 px-4 py-3"):
                    name = user.display_name or user.username
                    with ui.element("div").classes(
                        "w-9 h-9 shrink-0 rounded-full bg-secondary flex items-center justify-center "
                        "text-amber-100 font-semibold shadow-xs"
                    ):
                        ui.label(name[:1].upper())
                    with ui.column().classes("gap-0 flex-grow min-w-0"):
                        ui.label(name).classes("text-sm font-medium text-white truncate")
                        ui.label(f"@{user.username}").classes("text-xs text-stone-400 truncate")
                    if user.is_admin:
                        ui.button(icon="admin_panel_settings", on_click=lambda: ui.navigate.to("/admin")).props(
                            "flat round dense"
                        ).classes("text-stone-400 hover:text-white shrink-0").tooltip("Quản trị")
                    ui.button(icon="logout", on_click=logout).props("flat round dense").classes(
                        "text-stone-400 hover:text-white shrink-0"
                    ).tooltip("Đăng xuất")

        # ---------------- Đồng bộ độ rộng thanh bên ----------------
        def on_sidebar_resized(e: Any) -> None:
            try:
                w = int(e.args.get("width", 265))
                if 180 <= w <= 1200:
                    drawer._props["width"] = w
            except Exception:
                pass

        ui.on("sidebar_resized", on_sidebar_resized)

        # ---------------- Khung chat ----------------
        def render_tool_group(tool_messages: list[Message]) -> None:
            """Gom toàn bộ các bước suy luận và gọi tool vào một khối collapse 2 tầng (Outer -> Inner per Tool)."""
            # Thu thập kết quả theo tool_call_id
            results_by_id: dict[str, ToolResultMessage] = {
                msg.tool_call_id: msg
                for msg in tool_messages
                if isinstance(msg, ToolResultMessage)
            }

            # Lập danh sách các bước gọi tool kèm kết quả
            steps: list[dict[str, Any]] = []
            for msg in tool_messages:
                if isinstance(msg, ToolCallMessage):
                    for tc in msg.tool_calls:
                        res = results_by_id.get(tc.id)
                        steps.append({
                            "call": tc,
                            "result": res,
                        })

            call_count = len(steps)
            label = f"Quá trình tra cứu & suy luận ({call_count} bước)" if call_count else "Quá trình tra cứu tư liệu"

            with ui.row().classes("w-full pl-11 my-1"):
                # TẦNG 1: Collapse tổng quan toàn bộ quá trình tra cứu
                with ui.expansion(label, icon="manage_search").props(
                    "dense header-class='text-xs font-semibold text-stone-700 select-none'"
                ).classes(
                    "w-full text-xs rounded-xl border border-stone-200/90 bg-stone-50/80 overflow-hidden shadow-xs hover:border-emerald-600/40 transition-colors"
                ):
                    with ui.column().classes("w-full p-2.5 gap-2.5 bg-white/70"):
                        if not steps:
                            ui.label("Không có thông tin chi tiết các bước.").classes("text-stone-400 text-xs italic")
                            return

                        for idx, step in enumerate(steps, start=1):
                            tc = step["call"]
                            res: ToolResultMessage | None = step["result"]
                            friendly_name, icon = _tool_info(tc.name)
                            label_short, _ = _describe_tool_call(tc)
                            is_error = res.is_error if res else False

                            header_text = f"Bước {idx}: {label_short}"
                            border_color = "border-red-300 bg-red-50/40" if is_error else "border-stone-200 bg-stone-50/60 hover:bg-emerald-50/30"
                            header_color = "text-red-700" if is_error else "text-stone-800"

                            # TẦNG 2: Sub-collapse cho từng công cụ gọi và kết quả trả về
                            with ui.expansion(header_text, icon=icon).props(
                                f"dense header-class='text-xs font-medium {header_color} select-none'"
                            ).classes(
                                f"w-full text-xs rounded-lg border {border_color} overflow-hidden transition-all shadow-2xs"
                            ):
                                with ui.column().classes("w-full p-3 gap-2.5 bg-white"):
                                    # Phần 1: Tham số gọi công cụ
                                    with ui.column().classes("w-full gap-1"):
                                        with ui.row().classes("items-center gap-1.5"):
                                            ui.icon("input", size="14px").classes("text-stone-500")
                                            ui.label("Tham số gọi công cụ:").classes("text-[11px] font-semibold text-stone-600 uppercase tracking-wider")
                                        with ui.element("div").classes("w-full bg-stone-50 border border-stone-200/80 rounded-md p-2"):
                                            for k, v in tc.kwargs.items():
                                                with ui.row().classes("w-full no-wrap gap-2 text-xs"):
                                                    ui.label(f"{k}:").classes("font-semibold text-stone-600 shrink-0")
                                                    ui.label(str(v)).classes("font-mono text-stone-800 break-all")

                                    # Phần 2: Kết quả trả về
                                    with ui.column().classes("w-full gap-1 mt-1"):
                                        with ui.row().classes("items-center gap-1.5"):
                                            res_badge_icon = "error_outline" if is_error else "check_circle"
                                            badge_color = "text-red-600" if is_error else "text-emerald-700"
                                            ui.icon(res_badge_icon, size="14px").classes(badge_color)
                                            res_label = "Thông báo lỗi:" if is_error else "Kết quả tra cứu trả về:"
                                            ui.label(res_label).classes(f"text-[11px] font-semibold {badge_color} uppercase tracking-wider")

                                        res_text = parts_to_text(res.content) if res else "Đang chờ kết quả..."
                                        ui.label(res_text).classes(
                                            "w-full text-xs text-stone-800 whitespace-pre-wrap font-mono "
                                            "bg-stone-50/90 border border-stone-200 rounded-md p-2.5 "
                                            "max-h-72 overflow-y-auto leading-relaxed shadow-inner"
                                        )

        def render_message(message: Message) -> None:
            if isinstance(message, UserMessage):
                with ui.row().classes("w-full justify-end"):
                    ui.label(parts_to_text(message.content)).classes(
                        "bg-primary text-white px-4 py-2.5 rounded-2xl rounded-br-md max-w-[80%] "
                        "whitespace-pre-wrap shadow-sm leading-relaxed"
                    )
            elif isinstance(message, AssistantMessage):
                with ui.row().classes("w-full no-wrap gap-3 items-start"):
                    with ui.element("div").classes(
                        "w-8 h-8 shrink-0 rounded-full bg-emerald-100 border border-emerald-200 flex items-center justify-center shadow-xs"
                    ):
                        ui.icon("history_edu", size="18px").classes("text-primary")
                    ui.markdown(parts_to_text(message.content)).classes(
                        "chat-markdown text-stone-800 leading-relaxed pt-1 min-w-0 flex-grow"
                    )
            elif isinstance(message, (ToolCallMessage, ToolResultMessage)):
                render_tool_group([message])

        def fill_suggestion(text: str) -> None:
            message_input.value = text
            message_input.run_method("focus")

        @ui.refreshable
        def chat_view() -> None:
            if not state["messages"] and not state["pending_text"]:
                with ui.column().classes("w-full items-center text-center gap-3 pt-16 pb-8 max-w-2xl mx-auto"):
                    with ui.element("div").classes(
                        "w-16 h-16 rounded-2xl bg-emerald-100 border border-emerald-200 flex items-center justify-center shadow-sm"
                    ):
                        ui.icon("history_edu", size="34px").classes("text-primary")
                    ui.label(f"Xin chào, {user.display_name or user.username}!").classes(
                        "text-2xl font-bold text-stone-800"
                    )
                    ui.label(
                        "Chào mừng bạn đến với VNHisChat — Trợ lý AI chuyên sâu về Lịch sử và Địa lý Việt Nam. "
                        "Mọi câu hỏi đều được tra cứu đối chiếu và trích dẫn kiểm chứng từ Bộ 15 tập Lịch sử Việt Nam."
                    ).classes("text-stone-600 text-sm leading-relaxed max-w-lg")
                    ui.label("Gợi ý câu hỏi tiêu biểu:").classes("text-xs font-semibold uppercase tracking-wider text-stone-400 mt-4")
                    with ui.column().classes("w-full gap-2 items-center mt-1"):
                        for suggestion in SUGGESTIONS:
                            with ui.button(
                                on_click=lambda s=suggestion: fill_suggestion(s)
                            ).props("outline no-caps").classes(
                                "text-stone-700 text-sm normal-case bg-white border-stone-200 hover:border-emerald-600 hover:text-emerald-800 rounded-xl px-4 py-2.5 text-left w-full max-w-xl transition-all shadow-xs"
                            ):
                                with ui.row().classes("items-center gap-2.5 no-wrap w-full"):
                                    ui.icon("auto_stories", size="16px").classes("text-primary shrink-0")
                                    ui.label(suggestion).classes("flex-1 text-sm font-normal")
                return

            # Nhóm các message: gom các tool call/result liên tiếp trước câu trả lời thành 1 khối collapse duy nhất
            grouped: list[tuple[str, Any]] = []
            current_tools: list[Message] = []

            for msg in state["messages"]:
                if isinstance(msg, (ToolCallMessage, ToolResultMessage)):
                    current_tools.append(msg)
                else:
                    if current_tools:
                        grouped.append(("tools", current_tools))
                        current_tools = []
                    grouped.append(("single", msg))

            if current_tools:
                grouped.append(("tools", current_tools))

            with ui.column().classes("w-full gap-5"):
                for item_type, item_data in grouped:
                    if item_type == "tools":
                        render_tool_group(item_data)
                    else:
                        render_message(item_data)

                if state["pending_text"]:
                    # Tin nhắn vừa gửi, hiển thị ngay trong lúc chờ Agent trả lời
                    render_message(UserMessage(content=[TextPart(text=state["pending_text"])]))
                    with ui.row().classes("w-full no-wrap gap-3 items-center"):
                        with ui.element("div").classes(
                            "w-8 h-8 shrink-0 rounded-full bg-emerald-100 border border-emerald-200 flex items-center justify-center"
                        ):
                            ui.icon("history_edu", size="18px").classes("text-primary")
                        with ui.element("div").classes("typing flex gap-1"):
                            for _ in range(3):
                                ui.element("span")

        @ui.refreshable
        def chat_header() -> None:
            ui.label(current_title()).classes("text-sm font-semibold text-stone-700 truncate")

        def scroll_to_bottom() -> None:
            message_scroll.scroll_to(percent=1.0, duration=0.2)

        # ---------------- Gửi tin nhắn ----------------
        async def send() -> None:
            text = (message_input.value or "").strip()
            if not text or state["pending_text"]:
                return
            if not provider_select.value:
                ui.notify("Chưa có model nào được bật. Hãy nhờ quản trị viên thêm model.", type="warning")
                return

            message_input.value = ""
            state["pending_text"] = text
            send_button.disable()
            chat_view.refresh()
            scroll_to_bottom()
            try:
                if state["conversation_id"] is None:
                    conversation = usecases.create_conversation.execute(token, _make_title(text))
                    state["conversation_id"] = conversation.id
                    ui.navigate.history.replace(f"/?c={conversation.id}")
                    persist_ui_state()
                    load_conversations()
                    chat_header.refresh()

                result = await run.io_bound(
                    usecases.send_message.execute,
                    token,
                    state["conversation_id"],
                    text,
                    provider_select.value,
                    model_select.value,
                    reasoning_select.value,
                    list(builtin_select.value or []) if builtin_switch.value else [],
                    approver=WebApprover(asyncio.get_running_loop(), page_root),
                )
                state["messages"].extend(result.new_messages)
                load_conversations()
            except Exception as exc:  # noqa: BLE001 - mọi lỗi đều phải báo cho người dùng
                message_input.value = text  # Trả lại nội dung để người dùng gửi lại
                handle_error(exc)
            finally:
                state["pending_text"] = None
                send_button.enable()
                chat_view.refresh()
                scroll_to_bottom()
                message_input.run_method("focus")

        # ---------------- Bố cục vùng chính ----------------
        with ui.column().classes("w-full h-screen no-wrap gap-0"):
            with ui.row().classes(
                "w-full items-center no-wrap gap-2 px-4 h-14 border-b border-stone-200 bg-white/90 backdrop-blur"
            ):
                ui.button(icon="menu", on_click=drawer.toggle).props("flat round dense").classes(
                    "text-stone-600"
                )
                chat_header()

            with ui.scroll_area().classes("flex-grow w-full") as message_scroll:
                with ui.column().classes("w-full max-w-3xl mx-auto px-4 py-6"):
                    chat_view()

            with ui.column().classes("w-full px-4 pb-4 pt-2"):
                with ui.card().classes(
                    "w-full max-w-3xl mx-auto p-2 rounded-2xl shadow-md border border-stone-200 gap-1 bg-white"
                ):
                    message_input = ui.textarea(placeholder="Hỏi về sự kiện, nhân vật, trận đánh hoặc địa lý lịch sử Việt Nam…").props(
                        "autogrow borderless dense input-class=px-2 input-style='max-height:200px'"
                    ).classes("w-full text-base")
                    with ui.row().classes("w-full items-center no-wrap gap-2 px-1"):
                        provider_select = ui.select(list(catalog), label="Nhà cung cấp").props(
                            "dense borderless options-dense"
                        ).classes("w-28 text-sm")
                        model_select = ui.select([], label="Model").props(
                            "dense borderless options-dense"
                        ).classes("w-44 text-sm")
                        reasoning_select = ui.select([], label="Suy luận").props(
                            "dense borderless options-dense"
                        ).classes("w-24 text-sm")
                        ui.separator().props("vertical").classes("my-2")
                        builtin_switch = ui.switch().props("dense").tooltip("Bật / tắt tool built-in")
                        builtin_select = ui.select([], label="Tool built-in", multiple=True).props(
                            "dense borderless options-dense"
                        ).classes("w-48 text-sm")
                        ui.space()
                        send_button = ui.button(icon="arrow_upward", on_click=send).props(
                            "unelevated round dense color=primary"
                        ).classes("shrink-0")
                ui.label(
                    "Dữ liệu được tra cứu và đối chiếu từ Bộ 15 tập Lịch sử Việt Nam (Viện Sử học 2017). "
                    "Vui lòng đối chiếu mã nguồn trích dẫn [Nguồn: tap_XX_trang_YYYY] để kiểm chứng."
                ).classes("w-full text-center text-xs text-stone-400 mt-2")

        message_input.on("keydown.enter.exact.prevent", send)

        # ---------------- Lựa chọn model ----------------
        def on_provider_change() -> None:
            if not provider_select.value:
                return
            labels = model_labels(catalog, provider_select.value)
            selection = default_selection(catalog)
            preferred = selection[1] if selection and selection[0] == provider_select.value else None
            model_select.set_options(labels, value=preferred if preferred in labels else next(iter(labels)))

        def on_model_change() -> None:
            if not model_select.value:
                return
            provider, model = provider_select.value, model_select.value

            modes = reasoning_modes(catalog, provider, model)
            reasoning_select.set_options(modes, value=default_reasoning(catalog, provider, model))
            reasoning_select.set_enabled(bool(modes))

            # Model có tool built-in thì mặc định bật và chọn hết, không có thì tắt và khóa
            tools_of_model = builtin_tools(catalog, provider, model)
            builtin_select.set_options(tools_of_model, value=list(tools_of_model))
            builtin_switch.value = bool(tools_of_model)
            builtin_switch.set_enabled(bool(tools_of_model))
            builtin_select.set_enabled(bool(tools_of_model))
            persist_ui_state()

        def on_builtin_switch_change() -> None:
            builtin_select.set_enabled(builtin_switch.value)
            persist_ui_state()

        provider_select.on_value_change(on_provider_change)
        model_select.on_value_change(on_model_change)
        reasoning_select.on_value_change(persist_ui_state)
        builtin_switch.on_value_change(on_builtin_switch_change)
        builtin_select.on_value_change(persist_ui_state)
        restore_ui_state(saved_ui)

        if not catalog:
            ui.notify("Chưa có model nào được bật. Hãy nhờ quản trị viên thêm model.", type="warning")
        if initial_error is not None:
            handle_error(initial_error)
        else:
            scroll_to_bottom()

    ui_run_kwargs.setdefault("title", f"{APP_NAME} — Hỏi Đáp Lịch Sử & Địa Lý Việt Nam")
    ui_run_kwargs.setdefault("reload", False)
    ui_run_kwargs.setdefault("favicon", "🎋")
    register_admin_pages(usecases=usecases, providers=providers, apply_theme=_apply_theme)

    ui.run(storage_secret=storage_secret, **ui_run_kwargs)
