from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import TypeVar, Generic

T = TypeVar("T", bound=BaseModel)


class Tool(ABC, Generic[T]):
    name: str
    description: str
    args_schema: type[T]

    @abstractmethod
    def invoke(self, tool_args: BaseModel):
        ...
