from history_agent.domain.state import ToolResult
from src.history_agent.domain.format.tool_description_prompt import ToolDescriptionPrompt
from src.history_agent.application.ports.tool_port import Tool


class ToolRegistry:
    def __init__(self, tools: list[Tool]):
        self._tools = {tool.name: tool for tool in tools}

    def _get_tool(self, name: str) -> Tool:
        return self._tools[name]

    def execute(self, tool_name: str, tool_args: dict) -> ToolResult:
        real_tool = self._get_tool(tool_name)
        real_tool.args_schema.model_validate(tool_args)
        result = real_tool.invoke()
        return ToolResult(
            tool_name=tool_name,
            arguments=tool_args,
            result=result,
        )

    def tools_describe(self) -> str:
        return "\n\n".join(
            ToolDescriptionPrompt(
                name=tool.name,
                description=tool.description,
                arguments=tool.args_schema.model_json_schema()
            )
            for tool in self._tools.values()
        )
