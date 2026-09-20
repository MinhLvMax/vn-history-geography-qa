import json
from pathlib import Path
from typing import Any


class FileService:
    @staticmethod
    def read_text(file_path: str | Path) -> str:
        """Đọc nội dung file text."""
        return Path(file_path).read_text(encoding="utf-8")

    @staticmethod
    def write_text(file_path: str | Path, content: str) -> None:
        """Ghi nội dung vào file text."""
        Path(file_path).write_text(content, encoding="utf-8")

    @staticmethod
    def read_json(file_path: str | Path) -> Any:
        """Đọc và parse file JSON."""
        with Path(file_path).open("r", encoding="utf-8") as file:
            return json.load(file)

    @staticmethod
    def write_json(
            file_path: str | Path,
            data: Any,
            indent: int = 4,
    ) -> None:
        """Ghi data vào file JSON."""
        with Path(file_path).open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=indent)
