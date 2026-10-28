"""Dịch vụ quản lý và thực thi công cụ."""

from typing import Any

from src.domain.exceptions import AppError, ToolDoesNotExist
from src.domain.models import ContentPart
from src.domain.ports import LoggerPort, NullLogger, Tool

# Các lỗi tool thường gặp khi Agent làm việc bình thường (được báo lại cho LLM để tự xử lý).
# ValueError bao gồm cả lỗi kiểm tra tham số của pydantic (ValidationError).
EXPECTED_TOOL_ERRORS = (AppError, OSError, ValueError)


class ToolExecutorService:
    """Application Service quản lý danh sách tools và điều phối thực thi."""

    def __init__(self, tools: list[Tool], logger: LoggerPort | None = None):
        self.tools_map: dict[str, Tool] = {tool.tool_name: tool for tool in tools}
        self.logger: LoggerPort = logger or NullLogger()

    def execute_a_tool(self, tool_name: str, **kwargs: Any) -> list[ContentPart]:
        """Tìm và thực thi tool theo tên, trả về danh sách các ContentPart kết quả."""
        self.logger.debug(f"Đang tìm kiếm tool: '{tool_name}' với tham số: {kwargs}")
        tool = self.tools_map.get(tool_name)
        if not tool:
            self.logger.warning(f"Không tìm thấy tool: '{tool_name}'")
            raise ToolDoesNotExist(f"Không tìm thấy tool nào với tên: {tool_name}")

        self.logger.info(f"Bắt đầu thực thi tool: '{tool_name}'")
        try:
            tool_result = tool.execute(**kwargs)
            parts = tool_result.to_parts()
            self.logger.info(f"Thực thi tool '{tool_name}' thành công, sinh ra {len(parts)} content part(s)")
            return parts
        except EXPECTED_TOOL_ERRORS as exc:
            # Lỗi nghiệp vụ đã lường trước (bị chặn quyền, file không tồn tại, tham số sai...): không cần traceback
            self.logger.warning(f"Tool '{tool_name}' không thực hiện được: {exc}")
            raise
        except Exception as exc:
            self.logger.error(f"Lỗi khi thực thi tool '{tool_name}': {exc}", exc_info=True)
            raise
