"""Shared runner helpers: path relativization, timed subprocess runs and file counting."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

from radar_audit.runner import RawToolOutput


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


_SKIPPED_DIRS = (".venv", "__pycache__", "node_modules", "vendor", "dist", "build")
SKIP_DIRNAMES = frozenset(_SKIPPED_DIRS)
# Same directories as glob suffixes, for tools that take exclude globs (radon, vulture).
SKIP_GLOB_SUFFIXES = tuple(f"/{name}/*" for name in _SKIPPED_DIRS)


def run_timed(
    command: list[str], timeout_s: int, cwd: Path | None = None
) -> tuple[subprocess.CompletedProcess[str], int]:
    """Run `command` capturing text output, and return it with its duration in milliseconds."""
    start = time.monotonic()
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=timeout_s)
    return completed, int((time.monotonic() - start) * 1000)


def raw_fallback(completed: subprocess.CompletedProcess[str]) -> dict[str, object]:
    """Raw stdout/stderr payload kept when a tool's output can't be parsed."""
    return {"stdout": completed.stdout, "stderr": completed.stderr}


def tool_output(
    command: list[str],
    raw_output: dict[str, object],
    completed: subprocess.CompletedProcess[str],
    duration_ms: int,
) -> RawToolOutput:
    """Build the RawToolOutput of one completed tool run."""
    return RawToolOutput(
        command=" ".join(command),
        raw_output=raw_output,
        exit_code=completed.returncode,
        duration_ms=duration_ms,
    )


def is_skipped(
    file_path: Path,
    target_path: Path,
    exclude_paths: list[Path],
    skip_dirnames: frozenset[str] = SKIP_DIRNAMES,
) -> bool:
    """Whether `file_path` sits under a skipped directory name or an excluded path."""
    relative_parts = file_path.relative_to(target_path).parts
    if any(part in skip_dirnames for part in relative_parts):
        return True
    return any(excluded == file_path or excluded in file_path.parents for excluded in exclude_paths)


def count_files(
    target_path: Path,
    exclude_paths: list[Path],
    glob: str = "*.py",
    suffixes: frozenset[str] | None = None,
    skip_dirnames: frozenset[str] = SKIP_DIRNAMES,
) -> int:
    """Count the files matching `glob` (and `suffixes`, if given) not skipped per `is_skipped`."""
    return sum(
        1
        for file_path in target_path.rglob(glob)
        if file_path.is_file()
        and (suffixes is None or file_path.suffix in suffixes)
        and not is_skipped(file_path, target_path, exclude_paths, skip_dirnames)
    )
