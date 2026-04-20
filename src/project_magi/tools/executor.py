"""Tool executor — read_file, grep_content, glob_files scoped to a root directory."""

from __future__ import annotations

import re
from pathlib import Path  # noqa: TC003 - used at runtime
from typing import Any

MAX_FILE_SIZE = 50 * 1024  # 50KB
MAX_OUTPUT_LINES = 200

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "read_file",
        "description": "Read the contents of a file. Output truncated at 50KB.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path relative to root directory"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "grep_content",
        "description": "Search for a regex pattern in files. Returns matching lines.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "path": {
                    "type": "string",
                    "description": "Directory to search in (relative to root, default: root)",
                },
                "glob": {
                    "type": "string",
                    "description": "File glob pattern to filter (e.g. '*.py')",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "glob_files",
        "description": "Find files matching a glob pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py')"},
                "path": {
                    "type": "string",
                    "description": "Directory to search in (relative to root, default: root)",
                },
            },
            "required": ["pattern"],
        },
    },
]


class ToolExecutor:
    """Executes tools scoped to a root directory."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir.resolve()

    def execute(self, name: str, input_data: dict[str, Any]) -> str:
        handlers = {
            "read_file": self._read_file,
            "grep_content": self._grep_content,
            "glob_files": self._glob_files,
        }
        handler = handlers.get(name)
        if not handler:
            return f"Error: unknown tool '{name}'"
        try:
            return handler(input_data)
        except Exception as e:
            return f"Error: {e}"

    def _resolve_path(self, relative: str) -> Path:
        resolved = (self.root_dir / relative).resolve()
        if not str(resolved).startswith(str(self.root_dir)):
            msg = f"Path '{relative}' is outside root directory"
            raise ValueError(msg)
        return resolved

    def _read_file(self, input_data: dict[str, Any]) -> str:
        path = self._resolve_path(input_data["path"])
        if not path.is_file():
            return f"Error: not a file: {input_data['path']}"
        content = path.read_text(errors="replace")
        if len(content) > MAX_FILE_SIZE:
            content = content[:MAX_FILE_SIZE] + "\n... [truncated at 50KB]"
        return content

    def _grep_content(self, input_data: dict[str, Any]) -> str:
        pattern = re.compile(input_data["pattern"])
        search_dir = self._resolve_path(input_data.get("path", "."))
        file_glob = input_data.get("glob", "*")

        matches: list[str] = []
        for file_path in sorted(search_dir.rglob(file_glob)):
            if not file_path.is_file():
                continue
            try:
                for i, line in enumerate(file_path.read_text(errors="replace").splitlines(), 1):
                    if pattern.search(line):
                        rel = file_path.relative_to(self.root_dir)
                        matches.append(f"{rel}:{i}: {line}")
                        if len(matches) >= MAX_OUTPUT_LINES:
                            matches.append(f"... [output capped at {MAX_OUTPUT_LINES} lines]")
                            return "\n".join(matches)
            except (OSError, UnicodeDecodeError):
                continue

        return "\n".join(matches) if matches else "No matches found."

    def _glob_files(self, input_data: dict[str, Any]) -> str:
        search_dir = self._resolve_path(input_data.get("path", "."))
        pattern = input_data["pattern"]

        # Use rglob for ** patterns, glob otherwise
        if "**" in pattern:
            files = sorted(search_dir.rglob(pattern.replace("**/", "")))
        else:
            files = sorted(search_dir.rglob(pattern))

        results = []
        for f in files:
            if f.is_file():
                results.append(str(f.relative_to(self.root_dir)))
                if len(results) >= MAX_OUTPUT_LINES:
                    results.append(f"... [output capped at {MAX_OUTPUT_LINES} entries]")
                    break

        return "\n".join(results) if results else "No files found."
