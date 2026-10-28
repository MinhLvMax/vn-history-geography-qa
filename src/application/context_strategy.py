"""Chiến lược quản lý và nén cửa sổ ngữ cảnh hội thoại."""

from __future__ import annotations

import json
from typing import Protocol, runtime_checkable

from src.domain.models import (
    Message,
    TextPart,
    ToolCallMessage,
    ToolResultMessage,
    UserMessage,
    parts_to_text,
)


@runtime_checkable
class ContextStrategyPort(Protocol):
    """Cổng chiến lược chuẩn bị lịch sử hội thoại trước khi đưa vào AgentContext."""

    def prepare_history(self, history: list[Message]) -> list[Message]:
        """Nhận lịch sử thô từ CSDL và trả về danh sách Message tối ưu cho LLM."""
        ...


class NoOpContextStrategy(ContextStrategyPort):
    """Chiến lược giữ nguyên 100% lịch sử (dùng khi muốn tắt cơ chế rút gọn bối cảnh)."""

    def prepare_history(self, history: list[Message]) -> list[Message]:
        return list(history)


class ObservationMaskingWindowStrategy(ContextStrategyPort):
    """Chiến lược Cửa sổ trượt kết hợp Observation Masking tổng quát cho mọi loại Tool."""

    def __init__(
        self,
        max_turns: int = 6,
        keep_raw_tool_turns: int = 1,
        max_history_chars: int = 7000,
        min_chars_to_mask: int = 400,
        max_highlights: int = 6,
        preview_chars: int = 200,
    ):
        """Khởi tạo chiến lược quản lý bối cảnh.

        Args:
            max_turns: Số lượt hỏi-đáp (Turn) tối đa giữ lại trong ngữ cảnh.
            keep_raw_tool_turns: Số lượt hoàn chỉnh gần nhất vẫn giữ nguyên văn 100% nội dung ToolResult.
            max_history_chars: Ngưỡng tổng số ký tự tối đa của lịch sử trước khi bắt buộc thu gọn cả lượt gần nhất.
            min_chars_to_mask: Chỉ thu gọn các ToolResult có độ dài vượt quá số ký tự này.
            max_highlights: Số dòng tiêu đề/đề mục tối đa giữ lại khi tóm tắt cấu trúc một ToolResult.
            preview_chars: Độ dài đoạn văn bản xem trước khi ToolResult không có các dòng tiêu đề cấu trúc.
        """
        self.max_turns = max(1, max_turns)
        self.keep_raw_tool_turns = max(0, keep_raw_tool_turns)
        self.max_history_chars = max(2000, max_history_chars)
        self.min_chars_to_mask = max(100, min_chars_to_mask)
        self.max_highlights = max(1, max_highlights)
        self.preview_chars = max(80, preview_chars)

    def prepare_history(self, history: list[Message]) -> list[Message]:
        if not history:
            return []

        turns = self._split_into_turns(history)

        # Bước 1: Cắt theo cửa sổ trượt `max_turns` lượt gần nhất
        window_turns = turns[-self.max_turns :]

        # Bước 2: Áp dụng Observation Masking cho các lượt cũ ngoài phạm vi `keep_raw_tool_turns`
        num_turns = len(window_turns)
        raw_cutoff_idx = max(0, num_turns - self.keep_raw_tool_turns)

        processed_turns: list[list[Message]] = []
        for idx, turn in enumerate(window_turns):
            if idx < raw_cutoff_idx:
                processed_turns.append(self._mask_turn_tool_results(turn))
            else:
                processed_turns.append(list(turn))

        # Bước 3: Kiểm tra tổng ngân sách ký tự (`max_history_chars`).
        # Nếu vẫn vượt ngưỡng, thu gọn tiếp ToolResult của các lượt còn lại từ cũ đến mới.
        for idx in range(raw_cutoff_idx, num_turns):
            if self._count_turns_chars(processed_turns) <= self.max_history_chars:
                break
            processed_turns[idx] = self._mask_turn_tool_results(processed_turns[idx])

        # Nếu vẫn còn vượt ngưỡng sau khi đã mask hết ToolResult, bỏ bớt các lượt cũ nhất
        while (
            len(processed_turns) > 1
            and self._count_turns_chars(processed_turns) > self.max_history_chars
        ):
            processed_turns.pop(0)

        return [msg for turn in processed_turns for msg in turn]

    @staticmethod
    def _split_into_turns(history: list[Message]) -> list[list[Message]]:
        """Chia danh sách Message phẳng thành các Turn (mỗi Turn bắt đầu bằng UserMessage)."""
        turns: list[list[Message]] = []
        current_turn: list[Message] = []

        for msg in history:
            if isinstance(msg, UserMessage) and current_turn:
                turns.append(current_turn)
                current_turn = [msg]
            else:
                current_turn.append(msg)

        if current_turn:
            turns.append(current_turn)
        return turns

    def _mask_turn_tool_results(self, turn: list[Message]) -> list[Message]:
        """Thu gọn các ToolResultMessage dài trong một Turn dựa trên ngữ cảnh ToolCall và cấu trúc văn bản."""
        calls_by_id: dict[str, ToolCallMessage.ToolCall] = {}
        for msg in turn:
            if isinstance(msg, ToolCallMessage):
                for tc in msg.tool_calls:
                    calls_by_id[tc.id] = tc

        masked_turn: list[Message] = []
        for msg in turn:
            if isinstance(msg, ToolResultMessage) and not msg.is_error:
                raw_text = parts_to_text(msg.content)
                if len(raw_text) > self.min_chars_to_mask:
                    matched_call = calls_by_id.get(msg.tool_call_id)
                    masked_turn.append(
                        self._create_masked_tool_result(msg, raw_text, matched_call)
                    )
                    continue
            masked_turn.append(msg)
        return masked_turn

    def _create_masked_tool_result(
        self,
        original: ToolResultMessage,
        raw_text: str,
        tool_call: ToolCallMessage.ToolCall | None = None,
    ) -> ToolResultMessage:
        """Tóm tắt tổng quát kết quả của bất kỳ Tool nào mà không phụ thuộc định dạng riêng của Tool."""
        call_desc = f"'{original.name}'"
        if tool_call and tool_call.kwargs:
            args_str = json.dumps(tool_call.kwargs, ensure_ascii=False)
            if len(args_str) > 120:
                args_str = args_str[:117] + "..."
            call_desc = f"'{original.name}({args_str})'"

        non_empty_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        lead_line = non_empty_lines[0] if non_empty_lines else ""
        if len(lead_line) > 160:
            lead_line = lead_line[:157] + "..."

        # Trích xuất các dòng tiêu đề/mục đánh dấu cấu trúc (nếu kết quả có chia mục hoặc danh sách)
        structural_lines: list[str] = []
        for line in non_empty_lines[1:]:
            if (
                line.startswith("---")
                or line.startswith("#")
                or line.startswith("- [")
                or line.startswith("* [")
                or (line[:2].isdigit() and line[1:3] in (". ", ") "))
            ):
                compact = line.strip("-# ").strip()
                if compact and compact not in structural_lines:
                    structural_lines.append(compact[:140])
            if len(structural_lines) >= self.max_highlights:
                break

        details: list[str] = []
        if lead_line:
            details.append(lead_line)
        if structural_lines:
            details.append("Các mục chính: " + " ; ".join(structural_lines))
        elif len(non_empty_lines) > 1:
            body_preview = " ".join(non_empty_lines[1:])[: self.preview_chars].strip()
            if body_preview:
                details.append(f"Trích đoạn: {body_preview}...")

        detail_text = " | ".join(details) if details else raw_text[: self.preview_chars].strip()
        summary = (
            f"[Kết quả từ công cụ {call_desc} ở lượt trước ({len(raw_text)} ký tự, "
            f"{len(non_empty_lines)} dòng) đã được thu gọn: {detail_text}. "
            f"Nếu cần xem lại chi tiết, hãy gọi lại công cụ tương ứng.]"
        )

        return ToolResultMessage(
            tool_call_id=original.tool_call_id,
            name=original.name,
            content=[TextPart(text=summary)],
            is_error=original.is_error,
        )

    @staticmethod
    def _count_turns_chars(turns: list[list[Message]]) -> int:
        total = 0
        for turn in turns:
            for msg in turn:
                if hasattr(msg, "content") and isinstance(msg.content, list):
                    total += len(parts_to_text(msg.content))
                elif hasattr(msg, "content") and isinstance(msg.content, str):
                    total += len(msg.content)
        return total
