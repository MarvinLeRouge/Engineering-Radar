"""Runner for tsc or vue-tsc, which type-checks the target's TypeScript project."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from radar_audit.runner import RawToolOutput
from radar_audit.runners.shared import count_files, is_skipped, run_timed, tool_output
from radar_audit.scope import TESTS_AND_MIGRATIONS

_DIAGNOSTIC_PATTERN = re.compile(
    r"^(?P<file>.+?)\((?P<line>\d+),(?P<column>\d+)\): error (?P<code>TS\d+): (?P<message>.+)$"
)
_SOURCE_EXTENSIONS = frozenset({".ts", ".tsx", ".vue"})
_SKIP_DIRNAMES = frozenset({"node_modules", "dist", "build"})


class TypeScriptRunner:
    """Runs an ephemeral tsc/vue-tsc against the target's own tsconfig.json (criterion 2.2)."""

    tool_name = "tsc"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"javascript"})
    scope: Literal["repo", "subproject"] = "subproject"
    excluded_zones = TESTS_AND_MIGRATIONS
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        """Runs tsc or vue-tsc with --noEmit against the target and parses its diagnostics."""
        if not (target_path / "tsconfig.json").exists():
            # No tsconfig.json means this JS subproject doesn't opt into
            # TypeScript checking at all; running tsc anyway would just print
            # its usage banner to stdout and exit 1, which downstream
            # normalizers would misread as "0 diagnostics on N files" (a
            # perfect score) instead of "not applicable" (discovered against
            # a real portfolio repo in Task 17 -- see spec §7's N/A guidance).
            return RawToolOutput(
                command="<skipped: no tsconfig.json>",
                raw_output={"diagnostics": [], "total_files": 0},
                exit_code=0,
                duration_ms=0,
            )

        package_json = target_path / "package.json"
        data = json.loads(package_json.read_text()) if package_json.exists() else {}
        package_name, binary_name = self._resolve_package_and_binary(data)

        command = ["npx", f"--package={package_name}", "--", binary_name, "--noEmit"]

        completed, duration_ms = run_timed(command, self.timeout_s, cwd=target_path)

        diagnostics = []
        for line in completed.stdout.splitlines():
            match = _DIAGNOSTIC_PATTERN.match(line.strip())
            # tsc checks what the project's tsconfig includes: out-of-scope files are dropped here.
            if match and not is_skipped(
                target_path / match.group("file"), target_path, exclude_paths, _SKIP_DIRNAMES
            ):
                diagnostics.append(
                    {
                        "file": match.group("file"),
                        "line": int(match.group("line")),
                        "column": int(match.group("column")),
                        "code": match.group("code"),
                        "message": match.group("message"),
                    }
                )

        total_files = count_files(
            target_path, exclude_paths, "*", _SOURCE_EXTENSIONS, _SKIP_DIRNAMES
        )
        return tool_output(
            command,
            {"diagnostics": diagnostics, "total_files": total_files},
            completed,
            duration_ms,
        )

    def _resolve_package_and_binary(self, package_json_data: dict[str, Any]) -> tuple[str, str]:
        dev_dependencies: dict[str, Any] = package_json_data.get("devDependencies", {})
        if "vue-tsc" in dev_dependencies:
            return "vue-tsc", "vue-tsc"
        return "typescript", "tsc"
