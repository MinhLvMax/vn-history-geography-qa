"""Application Context Strategy - Chiến lược quản lý bối cảnh hội thoại (Context Engineering).

Triển khai kiến trúc chuẩn công nghiệp (tương tự Claude Code / Anthropic Agent / SWE-agent):
1. Chia lịch sử thành các lượt hoàn chỉnh (Turn), mỗi Turn bắt đầu bằng một `UserMessage`
   (đảm bảo không bao giờ cắt rời giữa `ToolCallMessage` và `ToolResultMessage`).
2. Observation Masking:
   - Giữ nguyên văn 100% `ToolResultMessage` cho `keep_raw_tool_turns` lượt gần nhất
     để trả lời mượt các câu hỏi nối tiếp trực tiếp (follow-up).
   - Với các lượt cũ hơn, giữ nguyên `UserMessage`, `AssistantMessage` và `ToolCallMessage`,
     nhưng thu gọn nội dung dài của `ToolResultMessage` thành danh sách các mã nguồn `chunk_id`
     đã đọc (để nếu cần xem lại nguyên văn, Agent có thể gọi `get_vn_history_chunks_by_ids`).
3. Sliding Window + Character Budget:
   - Chỉ giữ tối đa `max_turns` lượt gần nhất và tự động thu gọn thêm nếu vượt ngân sách ký tự.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from src.domain.models import (
    Message,
    TextPart,
    ToolResultMessage,
    UserMessage,
    parts_to_text,
)

# Regex trích xuất mã nguồn dạng "Nguồn: tap_02_trang_0048" từ nội dung ToolResult
_SOURCE_ID_PATTERN = re.compile(r"Nguồn:\s*([A-Za-z0-9_\-]+)")


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
    """Chiến lược Cửa sổ trượt kết hợp Observation Masking (chuẩn Claude Code / SWE-agent)."""

    def __init__(
        self,
        max_turns: int = 6,
        keep_raw_tool_turns: int = 1,
        max_history_chars: int = 7000,
        min_chars_to_mask: int = 400,
    ):
        """Khởi tạo chiến lược quản lý bối cảnh.

        Args:
            max_turns: Số lượt hỏi-đáp (Turn) tối đa giữ lại trong ngữ cảnh.
            keep_raw_tool_turns: Số lượt hoàn chỉnh gần nhất vẫn giữ nguyên văn 100% nội dung ToolResult.
            max_history_chars: Ngưỡng tổng số ký tự tối đa của lịch sử trước khi bắt buộc thu gọn cả lượt gần nhất.
            min_chars_to_mask: Chỉ thu gọn các ToolResult có độ dài vượt quá số ký tự này.
        """
        self.max_turns = max(1, max_turns)
        self.keep_raw_tool_turns = max(0, keep_raw_tool_turns)
        self.max_history_chars = max(2000, max_history_chars)
        self.min_chars_to_mask = max(100, min_chars_to_mask)

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
        # Nếu vẫn vượt ngưỡng (ví dụ lượt liền trước lấy quá nhiều trang sách dài),
        # thu gọn tiếp ToolResult của các lượt còn lại từ cũ đến mới.
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
        """Thu gọn các ToolResultMessage dài trong một Turn thành bản tóm tắt mã nguồn."""
        masked_turn: list[Message] = []
        for msg in turn:
            if isinstance(msg, ToolResultMessage) and not msg.is_error:
                raw_text = parts_to_text(msg.content)
                if len(raw_text) > self.min_chars_to_mask:
                    masked_turn.append(self._create_masked_tool_result(msg, raw_text))
                    continue
            masked_turn.append(msg)
        return masked_turn

    @staticmethod
    def _create_masked_tool_result(
        original: ToolResultMessage, raw_text: str
    ) -> ToolResultMessage:
        """Tạo ToolResultMessage rút gọn nhưng giữ nguyên danh sách mã chunk_id đã tra cứu."""
        source_ids = list(dict.fromkeys(_SOURCE_ID_PATTERN.findall(raw_text)))
        if source_ids:
            sources_str = ", ".join(source_ids)
            summary = (
                f"[Nội dung tư liệu từ lượt trước đã được thu gọn để tối ưu bộ nhớ. "
                f"Các mã nguồn đã tra cứu: {sources_str}. "
                f"Nếu cần đọc lại nguyên văn, hãy gọi công cụ `get_vn_history_chunks_by_ids`.]"
            )
        else:
            preview = raw_text[:150].replace("\n", " ").strip()
            summary = (
                f"[Kết quả công cụ '{original.name}' ở lượt trước đã được thu gọn: {preview}...]"
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
