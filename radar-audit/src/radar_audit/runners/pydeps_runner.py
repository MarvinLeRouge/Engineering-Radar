"""Runner for pydeps, which reports the Python import graph for cycle detection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput
from radar_audit.runners.shared import raw_fallback, run_timed, tool_output


class PydepsRunner:
    """Reports the Python import graph via pydeps, used for cycle detection (criterion 1.1).

    Uses `--show-deps --no-output --max-bacon=0` rather than `--show-cycles`: live testing
    showed `--show-cycles` produces no usable stdout even against a genuine cycle, while
    `--show-deps` reliably returns a structured JSON import graph. Cycle detection itself
    runs in the normalizer (a DFS over each module's `imports` adjacency list), not here.

    Accuracy depends on `target_path` being an actual importable package root (contains
    `__init__.py`, its directory name matching the import style used inside it); see the
    plan's "Known limitation" note.
    """

    tool_name = "pydeps"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        """Runs pydeps in show-deps mode and returns its JSON import graph."""
        # exclude_paths is accepted for ToolRunner protocol conformance but unused here: pydeps
        # has no path-exclusion flag, and discover_subprojects only descends into non-dot
        # directories, so linked worktrees never reach this runner as a target_path anyway.
        command = ["uvx", "pydeps", str(target_path), "--show-deps", "--no-output", "--max-bacon=0"]

        completed, duration_ms = run_timed(command, self.timeout_s)

        try:
            raw_output: dict[str, object] = json.loads(completed.stdout)
        except json.JSONDecodeError:
            raw_output = raw_fallback(completed)

        return tool_output(command, raw_output, completed, duration_ms)
