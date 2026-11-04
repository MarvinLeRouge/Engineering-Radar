"""Runner for pytest with coverage, run through uvx against the target's dependencies."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Literal

import defusedxml.ElementTree as ET

from radar_audit.runner import RawToolOutput


class PytestCoverageRunner:
    """Runs pytest+coverage against the target's own runtime dependencies, ephemeral
    install via uvx (criterion 3.1, Python). Never reads a committed coverage.xml --
    always a live run, per quality-framework.md 3.5's evidence-freshness rule.
    """

    tool_name = "pytest-cov"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"python"})
    scope: Literal["repo", "subproject"] = "subproject"
    # A real suite takes minutes (Engineering-Radar: about 9); a ceiling, not a delay.
    timeout_s = 900

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        """Runs pytest with JUnit and coverage XML reports, then parses both."""
        with tempfile.TemporaryDirectory() as report_dir:
            junit_path = Path(report_dir) / "junit.xml"
            coverage_path = Path(report_dir) / "coverage.xml"

            command, env = self._launcher(target_path, Path(report_dir))
            command.extend(
                [
                    f"--junitxml={junit_path}",
                    f"--cov={target_path}",
                    f"--cov-report=xml:{coverage_path}",
                    # Nested subprojects (and worktrees) run as their own targets.
                    *(f"--ignore={excluded}" for excluded in exclude_paths),
                    str(target_path),
                ]
            )

            start = time.monotonic()
            try:
                completed = subprocess.run(
                    command,
                    cwd=target_path,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout_s,
                    env=env,
                )
            except (FileNotFoundError, OSError):
                # target_path doesn't exist or is inaccessible; treat as "no tests"
                duration_ms = int((time.monotonic() - start) * 1000)
                return RawToolOutput(
                    command=" ".join(command),
                    raw_output={
                        "tests": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
                        "failures": [],
                        "coverage_percent": None,
                    },
                    exit_code=1,
                    duration_ms=duration_ms,
                )
            duration_ms = int((time.monotonic() - start) * 1000)

            if not junit_path.exists():
                return RawToolOutput(
                    command=" ".join(command),
                    raw_output={
                        "tests": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
                        "failures": [],
                        "coverage_percent": None,
                    },
                    exit_code=completed.returncode,
                    duration_ms=duration_ms,
                )

            raw_output = self._parse_junit(junit_path)
            raw_output["coverage_percent"] = self._parse_coverage(coverage_path)

            return RawToolOutput(
                command=" ".join(command),
                raw_output=raw_output,
                exit_code=completed.returncode,
                duration_ms=duration_ms,
            )

    def _launcher(
        self, target_path: Path, scratch_dir: Path
    ) -> tuple[list[str], dict[str, str] | None]:
        """Command prefix running pytest with the target's own dependencies installed.

        A uv project (a pyproject.toml and a uv.lock in the target or an enclosing
        workspace of the same repository) runs through `uv run --frozen`, with its
        environment in a scratch directory so the audited repository is never modified;
        otherwise requirements files are passed to uvx.
        """
        if (target_path / "pyproject.toml").exists() and _has_uv_lock(target_path):
            env = {
                key: value
                for key, value in os.environ.items()
                # The audit's own virtualenv must not leak into the target's.
                if key != "VIRTUAL_ENV"
            }
            env["UV_PROJECT_ENVIRONMENT"] = str(scratch_dir / "venv")
            command = ["uv", "run", "--project", str(target_path), "--frozen"]
            return [*command, "--with", "pytest-cov", "pytest"], env
        command = ["uvx", "--with", "pytest-cov"]
        for name in ("requirements.txt", "requirements-dev.txt"):
            if (target_path / name).exists():
                command.extend(["--with-requirements", str(target_path / name)])
        return [*command, "pytest"], None

    def _parse_junit(self, junit_path: Path) -> dict[str, object]:
        root = ET.parse(junit_path).getroot()
        assert root is not None
        suite = root.find("testsuite") if root.tag == "testsuites" else root
        if suite is None:
            return {"tests": {"total": 0, "passed": 0, "failed": 0, "skipped": 0}, "failures": []}

        total = int(suite.get("tests", 0))
        failures = int(suite.get("failures", 0))
        errors = int(suite.get("errors", 0))
        skipped = int(suite.get("skipped", 0))

        failed_cases = []
        for testcase in suite.findall("testcase"):
            if testcase.find("failure") is not None or testcase.find("error") is not None:
                classname = testcase.get("classname")
                failed_cases.append(
                    {
                        # pytest's default --junitxml has no file/line attribute on
                        # <testcase> (only classname/name/time) -- best-effort derive
                        # a file path from classname, leave line unavailable.
                        "file": classname.replace(".", "/") + ".py" if classname else None,
                        "name": testcase.get("name"),
                        "line": None,
                    }
                )

        return {
            "tests": {
                "total": total,
                "passed": total - failures - errors - skipped,
                "failed": failures + errors,
                "skipped": skipped,
            },
            "failures": failed_cases,
        }

    def _parse_coverage(self, coverage_path: Path) -> float | None:
        if not coverage_path.exists():
            return None
        root = ET.parse(coverage_path).getroot()
        assert root is not None
        line_rate = root.get("line-rate")
        return round(float(line_rate) * 100, 2) if line_rate is not None else None


def _has_uv_lock(target_path: Path) -> bool:
    """Whether a uv.lock sits in the target or an ancestor, without leaving its git repository.

    Stopping at the repository root keeps an unrelated uv.lock higher up (a home-directory
    project, a parent workspace) from turning a requirements-based repository into a uv one.
    """
    for directory in (target_path, *target_path.parents):
        if (directory / "uv.lock").exists():
            return True
        if (directory / ".git").exists():
            return False
    return False
