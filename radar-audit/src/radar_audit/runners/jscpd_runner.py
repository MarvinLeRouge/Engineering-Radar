"""Runner for jscpd, which detects code duplication across source files."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput
from radar_audit.runners.shared import raw_fallback, run_timed, tool_output
from radar_audit.scope import TESTS_AND_MIGRATIONS, exclusion_glob

_ALWAYS_EXCLUDED_DIRNAMES = (
    "node_modules",
    "vendor",
    "dist",
    "build",
    "docs",
)
_DOT_DIRECTORY_IGNORE_SUFFIX = "**/.*/**"
# Code duplication (criterion 2.5) means source code, not prose: without an
# explicit --format, jscpd also scans markdown and other text formats by
# default, which flags things like a bash example block mirrored between
# README.md and README.fr.md as a "duplicate" -- a false positive, not a
# code-quality issue. Scoped to this portfolio's actual stacks (toolchain.md).
_SOURCE_FORMATS = ("javascript", "jsx", "typescript", "tsx", "vue", "php", "python")


class JscpdRunner:
    """Runs jscpd for cross-language code duplication detection (criterion 2.5)."""

    tool_name = "jscpd"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset()
    scope: Literal["repo", "subproject"] = "repo"
    excluded_zones = TESTS_AND_MIGRATIONS
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        """Runs jscpd over the repo's source formats and returns its JSON duplication report."""
        with tempfile.TemporaryDirectory() as report_dir:
            ignore_patterns = [f"{target_path}/**/{name}/**" for name in _ALWAYS_EXCLUDED_DIRNAMES]
            ignore_patterns.append(f"{target_path}/{_DOT_DIRECTORY_IGNORE_SUFFIX}")
            for excluded in exclude_paths:
                ignore_patterns.append(exclusion_glob(excluded, excluded, "/**"))

            command = [
                "npx",
                "--package=jscpd",
                "--",
                "jscpd",
                "--reporters",
                "json",
                "--output",
                report_dir,
                "--silent",
                "--format",
                ",".join(_SOURCE_FORMATS),
                "--ignore",
                ",".join(ignore_patterns),
                str(target_path),
            ]

            completed, duration_ms = run_timed(command, self.timeout_s)

            report_path = Path(report_dir) / "jscpd-report.json"
            if not report_path.exists():
                return tool_output(command, raw_fallback(completed), completed, duration_ms)
            raw_output = json.loads(report_path.read_text())

        return tool_output(command, raw_output, completed, duration_ms)
