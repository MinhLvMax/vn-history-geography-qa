"""Kiểm tra khả năng tương thích của mô hình với chế độ suy luận."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class ProbeResult:
    """Kết quả kiểm tra một cặp (model, chế độ suy luận)."""
    ok: bool
    message: str
    elapsed_ms: int


@runtime_checkable
class ModelProbePort(Protocol):
    """Hợp đồng kiểm tra model (triển khai ở tầng Infrastructure, gọi API thật)."""

    def probe(
        self,
        provider: str,
        model_code: str,
        reasoning: str | None,
        builtin_tools: list[str],
    ) -> ProbeResult:
        """Gửi một yêu cầu rất ngắn và trả về kết quả; không ném lỗi, mọi lỗi nằm trong ProbeResult."""
        ...
