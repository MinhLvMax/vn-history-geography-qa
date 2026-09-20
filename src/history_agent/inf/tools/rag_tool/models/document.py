from typing import Any
from dataclasses import dataclass


@dataclass
class Document:
    '''Không cần quan tâm đến vị trí của nó lắm vì khi triển khai 1 port thì kiểu gì cũng phải mò đến nó'''
    id: str
    text: str
    metadata: dict[str, Any]
