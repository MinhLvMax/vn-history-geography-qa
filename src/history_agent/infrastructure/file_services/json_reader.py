import json
from pathlib import Path


class JsonReader:
    def read(self, file_path: str) -> dict:
        path = Path(file_path)

        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
