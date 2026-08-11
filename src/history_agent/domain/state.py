from pydantic import BaseModel, Field
from enum import Enum


class Role(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Message(BaseModel):
    role: Role
    content: str


class ToolResult(BaseModel):
    tool_name: str
    arguments: dict
    result: dict | None = None
    success: bool = True
    error: str | None = None


class State(BaseModel):
    messages: list[Message] = Field(default_factory=list)
    tool_results: list[ToolResult] = Field(default_factory=list)

    def get_messages(self) -> list[dict]:
        '''
        Trả về hội thoại dạng list dict
        :return:
        '''
        return [
            message.model_dump()
            for message in self.messages
        ]

    def get_tool_results(self) -> list[dict]:
        '''
        Trả về danh sách kết quả tool dạng list dict
        :return:
        '''
        return [
            tool_result.model_dump()
            for tool_result in self.tool_results
        ]
