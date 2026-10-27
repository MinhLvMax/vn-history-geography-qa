"""Application Approval - Cổng (Port) xin xác nhận của người dùng cho các thao tác nhạy cảm.

AgentService gắn "người xác nhận" của phiên hiện tại vào phạm vi chạy tool (contextvar);
tool / PathPolicy gọi request_approval() khi cần (vd. ghi ra ngoài workspace).
Quyết định không đi qua tham số tool nên LLM không thể tự bỏ qua bước xác nhận.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Protocol, runtime_checkable


@runtime_checkable
class ApprovalPort(Protocol):
    """Hỏi người dùng có cho phép một thao tác hay không (chặn cho tới khi có câu trả lời)."""

    def confirm(self, title: str, details: str) -> bool:
        ...


_current_approver: ContextVar[ApprovalPort | None] = ContextVar("current_approver", default=None)


@contextmanager
def approval_scope(approver: ApprovalPort | None) -> Iterator[None]:
    """Gắn người xác nhận cho các tool chạy bên trong khối with."""
    token = _current_approver.set(approver)
    try:
        yield
    finally:
        _current_approver.reset(token)


def request_approval(title: str, details: str) -> bool:
    """Xin xác nhận. Không có giao diện xác nhận (vd. CLI, chạy nền) thì coi như từ chối."""
    approver = _current_approver.get()
    return bool(approver is not None and approver.confirm(title, details))
