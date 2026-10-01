from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput
from radar_audit.runners.docker_support import run_docker_command


class ActionlintRunner:
    """Lints GitHub Actions workflows with actionlint (criterion 7.1)."""

    tool_name = "actionlint"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset()
    scope: Literal["repo", "subproject"] = "repo"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        completed, duration_ms = run_docker_command(
            [
                "-v",
                f"{target_path}:/repo:ro",
                "-w",
                "/repo",
                "rhysd/actionlint:latest",
                "-format",
                "{{json .}}",
            ],
            timeout_s=self.timeout_s,
        )

        findings = self._parse_findings(completed.stdout)
        if findings is None:
            return RawToolOutput(
                command="docker run ... actionlint -format '{{json .}}'",
                raw_output={"error": completed.stderr.strip()},
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

        return RawToolOutput(
            command="docker run ... actionlint -format '{{json .}}'",
            raw_output={"findings": findings},
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )

    @staticmethod
    def _parse_findings(stdout: str) -> list[dict[str, object]] | None:
        try:
            findings = json.loads(stdout.strip())
        except json.JSONDecodeError:
            return None
        return findings if isinstance(findings, list) else None
