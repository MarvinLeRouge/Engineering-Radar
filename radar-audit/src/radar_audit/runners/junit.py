"""Shared JUnit XML parsing and empty-result shapes for the test runners."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import defusedxml.ElementTree as ET

from radar_audit.runner import RawToolOutput

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element


def zero_test_results() -> dict[str, object]:
    """Fresh "no test ran" tests/failures payload, without coverage."""
    return {"tests": {"total": 0, "passed": 0, "failed": 0, "skipped": 0}, "failures": []}


def no_report_output(command: list[str], exit_code: int, duration_ms: int) -> RawToolOutput:
    """RawToolOutput for a test run that left no usable report: zero tests, no coverage."""
    return RawToolOutput(
        command=" ".join(command),
        raw_output={**zero_test_results(), "coverage_percent": None},
        exit_code=exit_code,
        duration_ms=duration_ms,
    )


def parse_junit(
    junit_path: Path,
    case_file: Callable[[Element], str | None],
    *,
    recursive: bool,
) -> dict[str, object]:
    """Parse a JUnit report's first suite into test counts and failed cases.

    `case_file` derives a failed testcase's file from its attributes; `recursive`
    collects nested testcases too instead of the suite's direct children only.
    Raises ET.ParseError on an unparseable or empty report.
    """
    root = ET.parse(junit_path).getroot()
    assert root is not None
    suite = root.find("testsuite") if root.tag == "testsuites" else root
    if suite is None:
        return zero_test_results()

    total = int(suite.get("tests", 0))
    failures = int(suite.get("failures", 0))
    errors = int(suite.get("errors", 0))
    skipped = int(suite.get("skipped", 0))

    testcases = suite.iter("testcase") if recursive else suite.findall("testcase")
    failed_cases = [
        {"file": case_file(testcase), "name": testcase.get("name"), "line": None}
        for testcase in testcases
        if testcase.find("failure") is not None or testcase.find("error") is not None
    ]

    return {
        "tests": {
            "total": total,
            "passed": total - failures - errors - skipped,
            "failed": failures + errors,
            "skipped": skipped,
        },
        "failures": failed_cases,
    }
