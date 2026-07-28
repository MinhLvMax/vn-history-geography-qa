from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from agent_app.domain.models import ToolResult
from agent_app.domain.ports import Tool


class ToolRegistry:
    def __init__(self, tools: Iterable[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}
        if not self._tools:
            raise ValueError("At least one tool must be registered.")

    def schemas(self) -> list[dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "arguments_schema": tool.args_schema.model_json_schema(),
            }
            for tool in self._tools.values()
        ]

    def execute(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        fingerprint = self.fingerprint(name, arguments)
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                tool_name=name,
                arguments=arguments,
                ok=False,
                error=f"Unknown tool '{name}'. Available: {sorted(self._tools)}",
                duration_ms=0,
                fingerprint=fingerprint,
            )

        started = time.perf_counter()
        try:
            validated = tool.args_schema.model_validate(arguments)
            data = tool.invoke(validated)
            return ToolResult(
                tool_name=name,
                arguments=arguments,
                ok=True,
                data=data,
                duration_ms=int((time.perf_counter() - started) * 1000),
                fingerprint=fingerprint,
            )
        except ValidationError as exc:
            error = f"Invalid arguments: {exc}"
        except Exception as exc:  # normalize infrastructure failures for the model
            error = f"Tool execution failed: {exc}"

        return ToolResult(
            tool_name=name,
            arguments=arguments,
            ok=False,
            error=error,
            duration_ms=int((time.perf_counter() - started) * 1000),
            fingerprint=fingerprint,
        )

    @staticmethod
    def fingerprint(name: str, arguments: dict[str, Any]) -> str:
        canonical = json.dumps(arguments, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(f"{name}:{canonical}".encode()).hexdigest()[:20]
