import json
from pathlib import Path


class JsonWriter:
    def write(self, content: dict, output_path: str) -> None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", encoding="utf-8") as f:
            json.dump(
                content,
                f,
                ensure_ascii=False,
                indent=4,
            )
