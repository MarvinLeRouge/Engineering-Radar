"""Runner for mypy, which type-checks Python subprojects."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput
from radar_audit.runners.shared import (
    anchored_path_regex,
    count_files,
    relativize_file_field,
    run_timed,
    tool_output,
)
from radar_audit.scope import TESTS_AND_MIGRATIONS


class MypyRunner:
    """Runs mypy (criterion 2.2, Python), branching on plugin detection per toolchain.md."""

    tool_name = "mypy"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    excluded_zones = TESTS_AND_MIGRATIONS
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        """Runs mypy in JSON output mode, adding plugin requirements when a plugin is configured."""
        if self._has_plugin(target_path):
            command = ["uvx", "--with", "mypy"]
            requirements = target_path / "requirements.txt"
            if requirements.exists():
                command.extend(["--with-requirements", str(requirements)])
            command.extend(["mypy", "--output=json", "--ignore-missing-imports"])
        else:
            command = ["uvx", "mypy", "--output=json", "--ignore-missing-imports"]

        if exclude_paths:
            for excluded in exclude_paths:
                try:
                    relative = excluded.relative_to(target_path)
                    # Use regex-escaped path for mypy's --exclude (which expects regex)
                    command.extend(["--exclude", anchored_path_regex(relative)])
                except ValueError:
                    pass  # not under target_path, skip

        command.append(str(target_path))

        completed, duration_ms = run_timed(command, self.timeout_s, cwd=target_path)

        diagnostics = []
        for line in completed.stdout.splitlines():
            try:
                diagnostics.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        relativize_file_field(diagnostics, target_path)
        total_files = count_files(target_path, exclude_paths)
        return tool_output(
            command,
            {"diagnostics": diagnostics, "total_files": total_files},
            completed,
            duration_ms,
        )

    def _has_plugin(self, target_path: Path) -> bool:
        pyproject = target_path / "pyproject.toml"
        if pyproject.exists():
            data = tomllib.loads(pyproject.read_text())
            if data.get("tool", {}).get("mypy", {}).get("plugins"):
                return True
        mypy_ini = target_path / "mypy.ini"
        if mypy_ini.exists() and "plugins" in mypy_ini.read_text():
            return True
        return False
