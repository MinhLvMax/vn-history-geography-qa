from typing import Protocol


class FileWriterPort(Protocol):
    def write(self, content, output_path):
        pass
