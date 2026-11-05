"""Runner for dependency-cruiser, which detects circular JS/TS module dependencies."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput
from radar_audit.runners.shared import anchored_path_regex, raw_fallback, run_timed, tool_output

# Directory names always excluded regardless of exclude_paths: --no-config disables
# dependency-cruiser's own default node_modules exclusion, and none of these hold
# code written by the audited project -- node_modules is vendored, vendor is
# PHP/Composer's dependency tree (which can bundle third-party JS), dist/build are
# compiled/bundled output (e.g. a Vite build under public/build).
_ALWAYS_EXCLUDED_DIRNAMES = ("node_modules", "vendor", "dist", "build")


class DependencyCruiserRunner:
    """Detects circular JS/TS dependencies via dependency-cruiser (criterion 1.1)."""

    tool_name = "dependency-cruiser"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        """Runs dependency-cruiser over the JS/TS subproject and returns its JSON output."""
        command = [
            "npx",
            "--package=dependency-cruiser",
            "--",
            "depcruise",
            "--no-config",
            "--output-type",
            "json",
        ]
        command.extend(["-x", self._build_exclude_pattern(target_path, exclude_paths)])
        command.append(".")

        completed, duration_ms = run_timed(command, self.timeout_s, cwd=target_path)

        try:
            raw_output: dict[str, object] = json.loads(completed.stdout)
        except json.JSONDecodeError:
            raw_output = raw_fallback(completed)

        return tool_output(command, raw_output, completed, duration_ms)

    def _build_exclude_pattern(self, target_path: Path, exclude_paths: list[Path]) -> str:
        relative_patterns = [rf"(^|/){re.escape(name)}(/|$)" for name in _ALWAYS_EXCLUDED_DIRNAMES]
        for excluded in exclude_paths:
            try:
                relative = excluded.relative_to(target_path)
            except ValueError:
                continue  # not under target_path, dependency-cruiser will never visit it
            relative_patterns.append(anchored_path_regex(relative))
        return "|".join(relative_patterns)
