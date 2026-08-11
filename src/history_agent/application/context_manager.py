from typing import Literal


class Message:
    def __init__(self, role: Literal['system', 'user', 'assistant'], content: str):
        self.role = role
        self.content = content


class ContextManager:
    def __init__(self, system_message: Message | None = None, messages: list[Message] | None = None):
        self.system_message = system_message
        self.messages = messages or []
        pass

    def add_message(self, message: Message):
        self.messages.append(message)

    def remove_message(self, message: Message):
        self.messages.remove(message)

    def get_last_message(self) -> Message | None:
        if self.messages and len(self.messages) > 0:
            return self.messages[-1]
        return None

    def get_history(self, count: int | None = None) -> list[Message]:
        history = self.messages if count is None else self.messages[-count:]

        if self.system_message is None:
            return history

        return [self.system_message, *history]

    def get_dict_history(self, count: int | None = None) -> list[dict[str, str]]:
        history = self.get_history(count)
        return [m.__dict__ for m in history]
