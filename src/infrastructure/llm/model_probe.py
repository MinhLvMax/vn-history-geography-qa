"""Infrastructure LLM - Kiểm tra model bằng cách gọi thật qua đúng adapter của hệ thống.

Dùng lại `build_llm` của Bootstrap để việc test đi đúng đường đang dùng khi chat thật.
"""

import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from typing import Callable

from src.application.model_probe import ModelProbePort, ProbeResult
from src.domain.models import AgentContext, AssistantMessage, TextPart, UserMessage
from src.domain.ports import LLMPort

PROBE_PROMPT = "Trả lời đúng một từ: OK"
MAX_MESSAGE_LENGTH = 300


class LlmModelProbe(ModelProbePort):
    """Triển khai ModelProbePort bằng LLMPort thật do Bootstrap tạo ra."""

    def __init__(self, build_llm: Callable[..., LLMPort], timeout_seconds: float = 60):
        self.build_llm = build_llm
        self.timeout_seconds = timeout_seconds

    def probe(
        self,
        provider: str,
        model_code: str,
        reasoning: str | None,
        builtin_tools: list[str],
    ) -> ProbeResult:
        started = time.monotonic()
        # Chạy trong luồng riêng để có thời gian chờ; SDK của nhà cung cấp có thể treo lâu
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self._call, provider, model_code, reasoning, builtin_tools)
        try:
            message = future.result(timeout=self.timeout_seconds)
            ok = True
        except FutureTimeoutError:
            message, ok = f"Quá thời gian chờ ({self.timeout_seconds:.0f}s)", False
        except Exception as exc:  # noqa: BLE001 - mọi lỗi của API đều cần hiển thị cho admin
            message, ok = f"{type(exc).__name__}: {exc}", False
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        elapsed_ms = int((time.monotonic() - started) * 1000)
        return ProbeResult(ok=ok, message=message[:MAX_MESSAGE_LENGTH], elapsed_ms=elapsed_ms)

    def _call(
        self,
        provider: str,
        model_code: str,
        reasoning: str | None,
        builtin_tools: list[str],
    ) -> str:
        llm = self.build_llm(
            provider=provider,
            model_name=model_code,
            reasoning=reasoning,
            builtin_tools=builtin_tools,
        )
        context = AgentContext(
            system_prompt="",
            history=[UserMessage(content=[TextPart(text=PROBE_PROMPT)])],
            tools=[],
        )
        decision = llm.decide(context)
        if isinstance(decision, AssistantMessage):
            return "OK: " + "".join(part.text for part in decision.content if isinstance(part, TextPart))
        return "OK: model trả về yêu cầu gọi tool"
