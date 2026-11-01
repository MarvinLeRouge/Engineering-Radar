"""Shared helpers that relativize file paths in tool output."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _to_relative(path_str: str, target_path: Path) -> str:
    """Convert an absolute path under `target_path` into a relative one.

    Falls back to the original string unchanged when it isn't an absolute
    path under `target_path` (already relative, or genuinely elsewhere) --
    some tools report relative paths natively, others don't, regardless of
    how the runner invoked them.
    """
    try:
        return str(Path(path_str).relative_to(target_path))
    except ValueError:
        return path_str


def relativize_file_field(
    items: list[dict[str, Any]], target_path: Path, key: str = "file"
) -> None:
    """Relativize `key` in place on every dict in `items` (e.g. a tool's own
    "findings"/"diagnostics" list), per `_to_relative`.
    """
    for item in items:
        value = item.get(key)
        if isinstance(value, str):
            item[key] = _to_relative(value, target_path)


def relativize_path_keys(mapping: dict[str, Any], target_path: Path) -> dict[str, Any]:
    """Return a new dict with every key (a file path) relativized, per
    `_to_relative` -- for tools (e.g. radon) whose own JSON uses the file
    path as the top-level key rather than a "file" field.
    """
    return {_to_relative(path, target_path): value for path, value in mapping.items()}
