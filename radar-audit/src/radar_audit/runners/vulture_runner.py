"""Runner for vulture, which detects dead code in Python projects."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput
from radar_audit.runners.shared import (
    SKIP_GLOB_SUFFIXES,
    relativize_file_field,
    run_timed,
    tool_output,
)
from radar_audit.scope import MIGRATIONS, exclusion_glob

_IGNORE_DECORATORS = "@app.command,@app.callback"
_LINE_PATTERN = re.compile(
    r"^(?P<file>.+):(?P<line>\d+): unused (?P<kind>\S+) '(?P<name>[^']+)' "
    r"\((?P<confidence>\d+)% confidence\)$"
)
_UNREACHABLE_CODE_PATTERN = re.compile(
    r"^(?P<file>.+):(?P<line>\d+): unreachable code after '(?P<after>[^']+)' "
    r"\((?P<confidence>\d+)% confidence\)$"
)


class VultureRunner:
    """Runs vulture's dead-code detection (criterion 5.2, Python)."""

    tool_name = "vulture"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    # Tests stay analyzed: code used only by tests is not dead (dead_code drops test findings).
    excluded_zones = frozenset({MIGRATIONS})
    timeout_s = 30

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        """Runs vulture over the target with audit ignore decorators and parses its findings."""
        patterns = [f"{target_path}{suffix}" for suffix in SKIP_GLOB_SUFFIXES]
        patterns.extend(exclusion_glob(excluded, excluded, "/*") for excluded in exclude_paths)
        command = [
            "uvx",
            "vulture",
            str(target_path),
            "--ignore-decorators",
            _IGNORE_DECORATORS,
            "--exclude",
            ",".join(patterns),
        ]

        # vulture prints paths relative to its cwd: pin it so they never depend on the caller.
        completed, duration_ms = run_timed(command, self.timeout_s, cwd=target_path)

        findings = []
        for line in completed.stdout.splitlines():
            stripped = line.strip()
            match = _LINE_PATTERN.match(stripped)
            if match:
                findings.append(
                    {
                        "file": match.group("file"),
                        "line": int(match.group("line")),
                        "kind": match.group("kind"),
                        "name": match.group("name"),
                        "confidence": int(match.group("confidence")),
                    }
                )
                continue
            unreachable_match = _UNREACHABLE_CODE_PATTERN.match(stripped)
            if unreachable_match:
                findings.append(
                    {
                        "file": unreachable_match.group("file"),
                        "line": int(unreachable_match.group("line")),
                        "kind": "unreachable_code",
                        "name": None,
                        "confidence": int(unreachable_match.group("confidence")),
                    }
                )

        relativize_file_field(findings, target_path)

        return tool_output(command, {"findings": findings}, completed, duration_ms)
