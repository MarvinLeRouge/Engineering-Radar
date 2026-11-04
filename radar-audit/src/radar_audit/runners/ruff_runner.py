"""Runner for Ruff's linter, which checks Python code with JSON output."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput
from radar_audit.runners.shared import (
    count_files,
    raw_fallback,
    relativize_file_field,
    run_timed,
    tool_output,
)
from radar_audit.scope import MIGRATIONS, exclusion_glob


class RuffRunner:
    """Runs Ruff's linter (criterion 2.1, Python)."""

    tool_name = "ruff-check"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    excluded_zones = frozenset({MIGRATIONS})
    timeout_s = 30

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        """Runs ruff check in JSON mode over the Python subproject and counts its files."""
        command = [
            "uvx",
            "ruff",
            "check",
            "--output-format=json",
            ".",
        ]
        if exclude_paths:
            relative_excludes = []
            for excluded in exclude_paths:
                try:
                    relative = excluded.relative_to(target_path)
                    relative_excludes.append(exclusion_glob(excluded, relative, "/**"))
                except ValueError:
                    pass  # not under target_path, skip
            if relative_excludes:
                command.extend(["--exclude", ",".join(relative_excludes)])

        completed, duration_ms = run_timed(command, self.timeout_s, cwd=target_path)

        try:
            violations = json.loads(completed.stdout)
        except json.JSONDecodeError:
            return tool_output(command, raw_fallback(completed), completed, duration_ms)

        relativize_file_field(violations, target_path, key="filename")
        total_files = count_files(target_path, exclude_paths)
        return tool_output(
            command, {"violations": violations, "total_files": total_files}, completed, duration_ms
        )
