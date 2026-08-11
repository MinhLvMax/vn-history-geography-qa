from src.agent_search.domain.format.tool_description_prompt import ToolDescriptionPrompt
from src.agent_search.application.tool_port import Tool


class ToolRegistry:
    def __init__(self, tools: list[Tool]):
        self._tools = {tool.name: tool for tool in tools}

    def get(self, name: str) -> Tool:
        return self._tools[name]

    def tools_describe(self) -> str:
        return "\n\n".join(
            ToolDescriptionPrompt(
                name=tool.name,
                description=tool.description,
                arguments=tool.args_schema.model_json_schema()
            )
            for tool in self._tools.values()
        )
