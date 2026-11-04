"""Runner for radon's cyclomatic complexity analysis of Python code."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput
from radar_audit.runners.shared import (
    SKIP_GLOB_SUFFIXES,
    raw_fallback,
    relativize_path_keys,
    run_timed,
    tool_output,
)
from radar_audit.scope import TESTS_AND_MIGRATIONS, exclusion_glob


class RadonComplexityRunner:
    """Runs radon's cyclomatic complexity analysis (criterion 2.3, Python)."""

    tool_name = "radon-cc"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    excluded_zones = TESTS_AND_MIGRATIONS
    timeout_s = 30

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        """Runs radon cc in JSON mode over the Python subproject, skipping vendored directories."""
        patterns = [f"{target_path}{suffix}" for suffix in SKIP_GLOB_SUFFIXES]
        patterns.extend(exclusion_glob(excluded, excluded, "/*") for excluded in exclude_paths)
        command = ["uvx", "radon", "cc", "--json", "-e", ",".join(patterns), str(target_path)]

        completed, duration_ms = run_timed(command, self.timeout_s)

        try:
            raw_output = relativize_path_keys(json.loads(completed.stdout), target_path)
        except json.JSONDecodeError:
            raw_output = raw_fallback(completed)

        return tool_output(command, raw_output, completed, duration_ms)
