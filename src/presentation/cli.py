"""Presentation CLI - Giao diện dòng lệnh tương tác với Agent.
"""

from typing import Callable

from src.application.agent_service import AgentServiceFactory
from src.application.context_strategy import ContextStrategyPort, NoOpContextStrategy
from src.domain.exceptions import AppError
from src.domain.models import (
    AgentContext,
    AssistantMessage,
    TextPart,
    UserMessage,
    parts_to_text,
)
from src.domain.ports import Tool
from src.presentation.model_catalog import (
    ModelCatalog,
    builtin_tools,
    default_reasoning,
    default_selection,
    model_labels,
    reasoning_modes,
)


def _choose(
    title: str,
    options: list[str],
    default: str | None = None,
    labels: dict[str, str] | None = None,
) -> str:
    """Hiển thị menu đánh số và trả về lựa chọn của người dùng (Enter = mặc định)."""
    labels = labels or {}
    default = default or options[0]
    print(f"\n{title}:")
    for index, option in enumerate(options, start=1):
        marker = " (mặc định)" if option == default else ""
        print(f"  {index}. {labels.get(option, option)}{marker}")

    while True:
        raw = input("Chọn số > ").strip()
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print("Lựa chọn không hợp lệ, vui lòng nhập lại.")


def _choose_model(load_catalog: Callable[[], ModelCatalog]) -> tuple[str, str, str | None, list[str]]:
    """Cho người dùng chọn nhà cung cấp → model → chế độ suy luận → bật tool built-in.

    Danh mục được nạp lại mỗi lần chọn để phản ánh thay đổi của quản trị viên.
    """
    catalog = load_catalog()
    if not catalog:
        raise AppError("Chưa có model nào được bật. Hãy nhờ quản trị viên thêm model.")

    selection = default_selection(catalog) or (list(catalog)[0], None)
    provider = _choose("Nhà cung cấp", list(catalog), default=selection[0])
    model_default = selection[1] if selection[0] == provider else None
    model = _choose(
        "Model",
        list(catalog[provider]),
        default=model_default,
        labels=model_labels(catalog, provider),
    )

    reasoning = None
    modes = reasoning_modes(catalog, provider, model)
    if modes:
        reasoning = _choose(
            "Chế độ suy luận", modes, default=default_reasoning(catalog, provider, model)
        )

    # Model có tool built-in thì mặc định bật hết
    selected_tools: list[str] = []
    tools_of_model = builtin_tools(catalog, provider, model)
    if tools_of_model:
        answer = input(f"\nBật tool built-in ({', '.join(tools_of_model)})? [Y/n] > ").strip().lower()
        if answer not in ("n", "no"):
            selected_tools = list(tools_of_model)

    print(
        f"\nĐang dùng: {provider} / {model} / {reasoning or '-'}"
        f" / built-in: {', '.join(selected_tools) or 'tắt'}"
    )
    return provider, model, reasoning, selected_tools


def run_cli(
    agent_service_factory: AgentServiceFactory,
    tools: list[Tool],
    system_prompt: str,
    model_catalog: Callable[[], ModelCatalog],
    context_strategy: ContextStrategyPort | None = None,
) -> None:
    """Khởi chạy phiên làm việc tương tác qua Console.

    Tất cả các phụ thuộc (agent_service_factory, tools, system_prompt, model_catalog)
    được tiêm trực tiếp từ bên ngoài,
    giúp tầng Presentation hoàn toàn độc lập với việc khởi tạo và cấu hình hệ thống.
    """
    strategy: ContextStrategyPort = context_strategy or NoOpContextStrategy()
    context = AgentContext(
        system_prompt=system_prompt,
        history=[],
        tools=tools,
    )

    print("=" * 60)
    print("   🎋 VNHisChat — HỎI ĐÁP LỊCH SỬ & ĐỊA LÝ VIỆT NAM")
    print("   Gõ '/model' để đổi model, 'exit' hoặc 'quit' để thoát")
    print("=" * 60)

    try:
        provider, model, reasoning, selected_tools = _choose_model(model_catalog)
    except AppError as exc:
        print(f"\n{exc}")
        return
    except (KeyboardInterrupt, EOFError):
        print("\nĐã hủy phiên làm việc.")
        return

    while True:
        try:
            user_input = input("\nUser > ").strip()
            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit"):
                print("Tạm biệt! Hẹn gặp lại.")
                break

            if user_input.lower() == "/model":
                provider, model, reasoning, selected_tools = _choose_model(model_catalog)
                continue

            context.history = strategy.prepare_history(context.history)
            user_message = UserMessage(content=[TextPart(text=user_input)])
            context.add_message(user_message)

            print("Thinking...")
            agent_service = agent_service_factory(provider, model, reasoning, selected_tools)
            result = agent_service.thinking(context)

            # Lấy message cuối cùng từ assistant
            last_message = result.messages[-1]
            if isinstance(last_message, AssistantMessage):
                reply_text = parts_to_text(last_message.content)
                print(f"\nAssistant > {reply_text}")
            else:
                print("\nAssistant > [Không có phản hồi dạng văn bản]")

        except (KeyboardInterrupt, EOFError):
            print("\nĐã hủy phiên làm việc.")
            break
        except AppError as exc:
            print(f"\n{exc}")
        except Exception as exc:
            print(f"\n[Lỗi trong quá trình xử lý]: {exc}")
