"""Runner for Pest, the PHP test framework, run from the target's local vendor/bin."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import defusedxml.ElementTree as ET

from radar_audit.runner import RawToolOutput
from radar_audit.runners.junit import no_report_output, parse_junit
from radar_audit.runners.shared import run_timed, tool_output

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element


class PestRunner:
    """Runs the target's own locally-installed Pest (criterion 3.1, PHP), native
    invocation via vendor/bin/pest -- same reasoning as PintRunner in 2.1. --min=0
    disables Pest's own coverage-threshold gate so exit_code reflects test pass/fail
    only. Never reads a committed coverage report -- always a live run.
    """

    tool_name = "pest"
    tool_version = "1.0.0"
    supported_stacks: frozenset[str] = frozenset({"php"})
    scope: Literal["repo", "subproject"] = "subproject"
    timeout_s = 120

    def run(self, target_path: Path, exclude_paths: list[Path]) -> RawToolOutput:
        """Runs the target's local Pest with JUnit and Clover reports, then parses both."""
        local_bin = target_path / "vendor" / "bin" / "pest"
        if not local_bin.exists():
            return RawToolOutput(
                command=f"pest (not installed at {local_bin})",
                raw_output={},
                exit_code=127,
                duration_ms=0,
            )

        with tempfile.TemporaryDirectory() as report_dir:
            junit_path = Path(report_dir) / "junit.xml"
            clover_path = Path(report_dir) / "clover.xml"

            command = [
                str(local_bin),
                f"--log-junit={junit_path}",
                "--coverage",
                f"--coverage-clover={clover_path}",
                "--min=0",
            ]

            completed, duration_ms = run_timed(command, self.timeout_s, cwd=target_path)

            # Pest writes an empty (0-byte) junit.xml -- not "file absent" -- when it
            # fails before running any test (e.g. a misconfigured/missing tests/
            # directory triggers "Test directory not found", exit 2). Guard against
            # both "no report file" and "unparseable/empty report file" the same way.
            no_usable_report = not junit_path.exists()
            if not no_usable_report:
                try:
                    # Pest's zero-tests case is a bare <testsuites/> with no child
                    # <testsuite> at all: parse_junit returns zero counts for it.
                    raw_output = parse_junit(junit_path, _pest_case_file, recursive=True)
                except ET.ParseError:
                    no_usable_report = True

            if no_usable_report:
                return no_report_output(command, completed.returncode, duration_ms)

            raw_output["coverage_percent"] = self._parse_clover(clover_path)

            return tool_output(command, raw_output, completed, duration_ms)

    def _parse_clover(self, clover_path: Path) -> float | None:
        if not clover_path.exists():
            return None
        root = ET.parse(clover_path).getroot()
        assert root is not None
        metrics = root.find(".//project/metrics")
        if metrics is None:
            return None
        statements = int(metrics.get("statements", 0))
        covered = int(metrics.get("coveredstatements", 0))
        if statements == 0:
            return None
        return round((covered / statements) * 100, 2)


def _pest_case_file(testcase: Element) -> str | None:
    """Pest's testcase file attribute is "path/to/Test.php::testname": strip the "::name"
    suffix. No line attribute is provided.
    """
    raw_file = testcase.get("file")
    return raw_file.split("::")[0] if raw_file else None
