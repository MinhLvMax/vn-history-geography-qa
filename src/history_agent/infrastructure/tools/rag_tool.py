from pydantic import BaseModel, Field
from src.history_agent.application.ports.tool_port import Tool
from src.history_agent.domain.state import ToolResult


class RagToolArgs(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=10)
    limit: int = Field(default=5, ge=1, le=50)


class RagTool(Tool):

    def __init__(self):
        self.name = self.__class__.__name__.lower()
        self.description = "Search and retrieve relevant information from the knowledge base using RAG."
        self.args_schema = RagToolArgs

    def execute(self, tool_args: BaseModel) -> ToolResult:
        pass
