from abc import ABC, abstractmethod
from pydantic import BaseModel


class Tool(ABC):
    name: str
    description: str
    args_schema: type[BaseModel]

    @abstractmethod
    def invoke(self, arguments: BaseModel) -> object:
        ...