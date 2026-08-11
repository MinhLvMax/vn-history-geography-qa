from typing import Protocol


class FileReaderPort(Protocol):
    def read(self, file_path) -> str:
        pass
