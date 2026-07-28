from __future__ import annotations

import pprint

import unicodedata
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from agent_app.infrastructure.tools.path_policy import PathPolicy


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


class SearchPathsArgs(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=10)
    kind: Literal["file", "directory", "any"] = "any"
    limit: int = Field(default=5, ge=1, le=50)


class SearchPathsTool:
    name = "search_paths"
    description = (
        "Search file and directory names below the configured archive root. "
        "Use multiple query variants in one call when useful."
    )
    args_schema = SearchPathsArgs

    def __init__(self, policy: PathPolicy) -> None:
        self._policy = policy

    def invoke(self, arguments: BaseModel) -> list[dict[str, object]]:
        args = SearchPathsArgs.model_validate(arguments)
        normalized_queries = [_normalize(query.strip()) for query in args.queries if query.strip()]
        matches: list[tuple[int, Path]] = []

        for path in self._policy.root.rglob("*"):
            if args.kind == "file" and not path.is_file():
                continue
            if args.kind == "directory" and not path.is_dir():
                continue

            name = _normalize(path.name)
            score = sum(2 if name == query else 1 for query in normalized_queries if query in name)
            if score:
                matches.append((score, path))

        matches.sort(key=lambda item: (-item[0], len(item[1].parts), str(item[1]).casefold()))
        return [
            {
                "path": self._policy.relative(path),
                "kind": "directory" if path.is_dir() else "file",
                "score": score,
            }
            for score, path in matches[: args.limit]
        ]


class ListChildrenArgs(BaseModel):
    path: str = Field(min_length=1)
    limit: int = Field(default=100, ge=1, le=500)


class ListChildrenTool:
    name = "list_children"
    description = "List direct children of a directory already identified inside the archive."
    args_schema = ListChildrenArgs

    def __init__(self, policy: PathPolicy) -> None:
        self._policy = policy

    def invoke(self, arguments: BaseModel) -> list[dict[str, str]]:
        args = ListChildrenArgs.model_validate(arguments)
        directory = self._policy.resolve(args.path)
        if not directory.is_dir():
            raise NotADirectoryError(args.path)

        children = sorted(directory.iterdir(), key=lambda path: (not path.is_dir(), path.name.casefold()))
        return [
            {
                "name": child.name,
                "path": self._policy.relative(child),
                "kind": "directory" if child.is_dir() else "file",
            }
            for child in children[: args.limit]
        ]


class ReadTextArgs(BaseModel):
    path: str = Field(min_length=1)
    max_chars: int = Field(default=8000, ge=100, le=50000)


class ReadTextTool:
    name = "read_text"
    description = "Read a bounded amount of UTF-8 text from an allowed archive file."
    args_schema = ReadTextArgs
    _allowed_suffixes = {".txt", ".md", ".json", ".csv", ".yaml", ".yml", ".log"}

    def __init__(self, policy: PathPolicy) -> None:
        self._policy = policy

    def invoke(self, arguments: BaseModel) -> dict[str, object]:
        args = ReadTextArgs.model_validate(arguments)
        path = self._policy.resolve(args.path)
        if not path.is_file():
            raise FileNotFoundError(args.path)
        if path.suffix.casefold() not in self._allowed_suffixes:
            raise ValueError(f"Unsupported text file type: {path.suffix}")

        text = path.read_text(encoding="utf-8", errors="replace")
        clipped = text[: args.max_chars]
        return {
            "path": self._policy.relative(path),
            "content": clipped,
            "truncated": len(clipped) < len(text),
            "total_chars": len(text),
        }
