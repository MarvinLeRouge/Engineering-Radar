import json
from pathlib import Path

import pytest
from radar_audit.runners import phpdoc_checker_runner
from radar_audit.runners.phpdoc_checker_runner import PhpdocCheckerRunner

from tests.git_helpers import init_git_repo

_DOCUMENTED_CLASS = (
    "<?php\n\n/**\n * Class A.\n */\nclass A\n{\n"
    "    /**\n     * Add two numbers.\n     *\n     * @param int $a\n     * @param int $b\n"
    "     * @return int\n     */\n    public function add(int $a, int $b): int\n    {\n"
    "        return $a + $b;\n    }\n}\n"
)

_UNDOCUMENTED_CLASS = (
    "<?php\n\nclass B\n{\n    public function subtract(int $a, int $b): int\n"
    "    {\n        return $a - $b;\n    }\n}\n"
)


@pytest.mark.slow
def test_reports_no_findings_on_a_fully_documented_class(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": _DOCUMENTED_CLASS})

    runner = PhpdocCheckerRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["findings"] == []


@pytest.mark.slow
def test_reports_class_and_method_findings_on_an_undocumented_class(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/B.php": _UNDOCUMENTED_CLASS})

    runner = PhpdocCheckerRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    types = {f["type"] for f in result.raw_output["findings"]}
    assert "class" in types
    assert "method" in types


@pytest.mark.slow
def test_excludes_paths_passed_via_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/A.php": _DOCUMENTED_CLASS,
            "src/excluded/B.php": _UNDOCUMENTED_CLASS,
        },
    )

    runner = PhpdocCheckerRunner()
    result = runner.run(repo_path / "src", exclude_paths=[repo_path / "src" / "excluded"])

    findings = result.raw_output["findings"]
    assert not any("excluded" in f["file"] for f in findings)


def test_reports_tool_identity():
    runner = PhpdocCheckerRunner()

    assert runner.tool_name == "phpdoc-checker"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"php"})


_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "runners" / "phpdoc-checker"


def test_wraps_real_phpdoc_checker_json_as_findings(tmp_path, fake_tool):
    stdout = (_FIXTURE_DIR / "undocumented-class.json").read_text()
    calls = fake_tool(phpdoc_checker_runner, stdout=stdout, returncode=1)

    result = PhpdocCheckerRunner().run(tmp_path, exclude_paths=[])

    assert [c[:2] for c in calls[:2]] == [["composer", "init"], ["composer", "require"]]
    assert calls[2][1:] == ["-d", str(tmp_path), "-x", "vendor", "-j"]
    assert calls[2][0].endswith("/vendor/bin/phpdoc-checker")
    assert result.command == " ".join(calls[2])
    assert result.exit_code == 1
    assert result.raw_output["findings"] == json.loads(stdout)
    assert {f["type"] for f in result.raw_output["findings"]} == {
        "class",
        "method",
        "param-missing",
        "return-missing",
    }


def test_joins_relative_exclusions_and_skips_paths_outside_the_target(tmp_path, fake_tool):
    calls = fake_tool(phpdoc_checker_runner, stdout="[]")

    PhpdocCheckerRunner().run(
        tmp_path,
        exclude_paths=[
            tmp_path / "src" / "excluded",
            tmp_path.parent / "elsewhere",
            tmp_path / "x.php",
        ],
    )

    assert calls[2][calls[2].index("-x") + 1] == "vendor,src/excluded,x.php"


def test_keeps_stdout_and_stderr_when_phpdoc_checker_output_is_not_json(tmp_path, fake_tool):
    fake_tool(phpdoc_checker_runner, stdout="PHP Warning", stderr="oops", returncode=255)

    result = PhpdocCheckerRunner().run(tmp_path, exclude_paths=[])

    assert result.exit_code == 255
    assert result.raw_output == {"stdout": "PHP Warning", "stderr": "oops"}
