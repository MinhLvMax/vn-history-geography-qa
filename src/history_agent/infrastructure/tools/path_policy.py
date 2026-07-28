from __future__ import annotations

from pathlib import Path

from agent_app.domain.errors import UnsafePathError


class PathPolicy:
    def __init__(self, root: Path) -> None:
        self.root = root.expanduser().resolve()

    def resolve(self, raw_path: str | Path) -> Path:
        path = Path(raw_path).expanduser()
        candidate = path.resolve() if path.is_absolute() else (self.root / path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise UnsafePathError(f"Path escapes archive root: {raw_path}") from exc
        return candidate

    def relative(self, path: Path) -> str:
        return str(path.resolve().relative_to(self.root))
