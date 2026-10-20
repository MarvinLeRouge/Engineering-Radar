from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Literal

from radar_audit.runner import RawToolOutput


class PintRunner:
    """Runs the target's own locally-installed Laravel Pint (criterion 2.1)."""

    tool_name = "pint"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"php"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 60

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        local_bin = target_path / "vendor" / "bin" / "pint"
        if not local_bin.exists():
            return RawToolOutput(
                command=f"pint (not installed at {local_bin})",
                raw_output={},
                exit_code=127,
                duration_ms=0,
            )

        command = [str(local_bin), "--test", "--format=json"]

        start = time.monotonic()
        completed = subprocess.run(
            command, cwd=target_path, capture_output=True, text=True, timeout=self.timeout_s
        )
        duration_ms = int((time.monotonic() - start) * 1000)

        try:
            parsed = json.loads(completed.stdout)
        except json.JSONDecodeError:
            parsed = None

        raw_output: dict[str, object]
        if not isinstance(parsed, dict):
            raw_output = {"stdout": completed.stdout, "stderr": completed.stderr}
        else:
            raw_output = parsed
            # Pint silently swaps its --format=json output for a different,
            # agent-only shape ({"tool": "pint", "result": ...}) when it detects
            # known AI-coding-agent env vars (CLAUDECODE, CLAUDE_CODE, AI_AGENT,
            # ...). Outside that detection it returns PHP-CS-Fixer's native json
            # report instead, which has no "result" key. The command always runs
            # with --test, so the outcome is binary: always set "result" from the
            # process exit code, overriding whatever either shape self-reports.
            raw_output["result"] = "passed" if completed.returncode == 0 else "fail"

        return RawToolOutput(
            command=" ".join(command),
            raw_output=raw_output,
            exit_code=completed.returncode,
            duration_ms=duration_ms,
        )
