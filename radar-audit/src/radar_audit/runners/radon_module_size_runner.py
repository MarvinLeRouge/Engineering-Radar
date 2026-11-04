"""Runner for radon's raw metrics, reporting per-file lines of code for Python modules."""

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


class RadonModuleSizeRunner:
    """Reports per-file LOC for Python modules via radon (criterion 1.3)."""

    tool_name = "radon-raw"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    excluded_zones = TESTS_AND_MIGRATIONS
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        """Runs radon raw in JSON mode and returns per-file line metrics, skipping vendored code."""
        # Exclude glob patterns must be absolute (matching `target_path`'s own form).
        # radon's exclude matching was empirically found not to match relative globs
        # when radon is invoked with an absolute target_path.
        patterns = [f"{target_path}{suffix}" for suffix in SKIP_GLOB_SUFFIXES]
        patterns.extend(exclusion_glob(excluded, excluded, "/*") for excluded in exclude_paths)

        command = ["uvx", "radon", "raw", "--json", "-e", ",".join(patterns), str(target_path)]

        completed, duration_ms = run_timed(command, self.timeout_s)

        try:
            raw_output: dict[str, object] = relativize_path_keys(
                json.loads(completed.stdout), target_path
            )
        except json.JSONDecodeError:
            raw_output = raw_fallback(completed)

        return tool_output(command, raw_output, completed, duration_ms)
