import subprocess
from pathlib import Path

import pytest
from radar_audit.runners import pest_runner
from radar_audit.runners.pest_runner import PestRunner

from tests.git_helpers import init_git_repo

_PHPUNIT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<phpunit xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:noNamespaceSchemaLocation="vendor/phpunit/phpunit/phpunit.xsd"
         bootstrap="vendor/autoload.php"
         colors="true"
>
    <testsuites>
        <testsuite name="Test Suite">
            <directory suffix="Test.php">./tests</directory>
        </testsuite>
    </testsuites>
    <source>
        <include>
            <directory>src</directory>
        </include>
    </source>
</phpunit>
"""

_CALCULATOR_PHP = """<?php

class Calculator
{
    public function add(int $a, int $b): int
    {
        return $a + $b;
    }
}
"""


def _install_local_pest(repo_path):
    (repo_path / "composer.json").write_text(
        '{"name": "fixture/fixture", "require-dev": {"pestphp/pest": "^3.0"}, '
        '"config": {"allow-plugins": {"pestphp/pest-plugin": true}}}\n'
    )
    subprocess.run(
        ["composer", "install", "--no-interaction"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )


@pytest.mark.slow
def test_reports_pass_and_coverage_on_passing_suite(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "phpunit.xml": _PHPUNIT_XML,
            "src/Calculator.php": _CALCULATOR_PHP,
            "tests/Unit/CalculatorTest.php": (
                "<?php\n\n"
                "require_once __DIR__ . '/../../src/Calculator.php';\n\n"
                "test('adds', function () {\n"
                "    $calculator = new Calculator();\n"
                "    expect($calculator->add(1, 2))->toBe(3);\n"
                "});\n"
            ),
        },
    )
    _install_local_pest(repo_path)

    runner = PestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["tests"]["passed"] == 1
    assert result.raw_output["tests"]["failed"] == 0
    assert result.raw_output["coverage_percent"] is not None


@pytest.mark.slow
def test_reports_failures_with_file(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "phpunit.xml": _PHPUNIT_XML,
            "src/Calculator.php": _CALCULATOR_PHP,
            "tests/Unit/CalculatorTest.php": (
                "<?php\n\n"
                "require_once __DIR__ . '/../../src/Calculator.php';\n\n"
                "test('adds', function () {\n"
                "    $calculator = new Calculator();\n"
                "    expect($calculator->add(1, 2))->toBe(4);\n"
                "});\n"
            ),
        },
    )
    _install_local_pest(repo_path)

    runner = PestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    assert result.raw_output["tests"]["failed"] == 1
    failures = result.raw_output["failures"]
    assert len(failures) == 1
    assert failures[0]["file"] == "tests/Unit/CalculatorTest.php"


@pytest.mark.slow
def test_reports_zero_collected_as_no_tests(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "phpunit.xml": _PHPUNIT_XML,
            "src/Calculator.php": _CALCULATOR_PHP,
            # A tests/ directory that exists but has no discoverable test file --
            # this is Pest's genuine "zero collected" case (exit 0, bare
            # <testsuites/> report). Omitting the tests/ directory entirely
            # instead makes Pest exit 2 with "Test directory not found", which
            # is a misconfiguration error, not a zero-tests result.
            "tests/Helper.php": "<?php\n// not a test file\n",
        },
    )
    _install_local_pest(repo_path)

    runner = PestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["tests"]["total"] == 0


@pytest.mark.slow
def test_reports_fallback_when_tests_directory_missing(tmp_path):
    """Pest writes a 0-byte junit.xml (not "file absent") and exits 2 when its
    configured tests/ directory doesn't exist -- verify the ParseError guard falls
    back to the contracted raw_output shape instead of crashing.
    """
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"phpunit.xml": _PHPUNIT_XML, "src/Calculator.php": _CALCULATOR_PHP},
    )
    _install_local_pest(repo_path)

    runner = PestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 2
    assert result.raw_output == {
        "tests": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
        "failures": [],
        "coverage_percent": None,
    }


def test_reports_missing_binary_as_unusable(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/Calculator.php": "<?php\n"})

    runner = PestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 127
    assert result.raw_output == {}


def test_reports_tool_identity():
    runner = PestRunner()

    assert runner.tool_name == "pest"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"php"})


_FIXTURES = Path(__file__).parent / "fixtures" / "runners" / "pest"


def _fake_local_pest(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/Calculator.php": "<?php\n"})
    bin_path = repo_path / "vendor" / "bin" / "pest"
    bin_path.parent.mkdir(parents=True)
    bin_path.touch()
    return repo_path


def _flag_path(command, prefix):
    return Path(next(arg for arg in command if arg.startswith(prefix)).split("=", 1)[1])


def _write_reports(junit=None, clover=None):
    def respond(command, cwd):
        if junit is not None:
            _flag_path(command, "--log-junit=").write_text(junit)
        if clover is not None:
            _flag_path(command, "--coverage-clover=").write_text(clover)

    return respond


def _read(name):
    return (_FIXTURES / name).read_text()


def test_parses_passing_junit_and_clover_coverage(tmp_path, fake_tool):
    repo_path = _fake_local_pest(tmp_path)
    calls = fake_tool(
        pest_runner,
        respond=_write_reports(_read("junit-pass.xml"), _read("clover-pass.xml")),
    )

    result = PestRunner().run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {
        "tests": {"total": 1, "passed": 1, "failed": 0, "skipped": 0},
        "failures": [],
        "coverage_percent": 100.0,
    }
    assert result.command == " ".join(calls[0])
    assert "--min=0" in calls[0]


def test_strips_test_name_suffix_from_failure_file(tmp_path, fake_tool):
    repo_path = _fake_local_pest(tmp_path)
    fake_tool(
        pest_runner,
        returncode=1,
        respond=_write_reports(_read("junit-fail.xml"), _read("clover-pass.xml")),
    )

    result = PestRunner().run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    assert result.raw_output["tests"] == {"total": 1, "passed": 0, "failed": 1, "skipped": 0}
    assert result.raw_output["failures"] == [
        {"file": "tests/Unit/CalculatorTest.php", "name": "adds", "line": None}
    ]


def test_failure_file_is_none_when_testcase_has_no_file_attribute(tmp_path, fake_tool):
    repo_path = _fake_local_pest(tmp_path)
    junit = _read("junit-fail.xml").replace(' file="tests/Unit/CalculatorTest.php::adds"', "")
    fake_tool(pest_runner, returncode=1, respond=_write_reports(junit))

    result = PestRunner().run(repo_path, exclude_paths=[])

    assert result.raw_output["failures"] == [{"file": None, "name": "adds", "line": None}]


def test_bare_testsuites_report_gives_zero_tests_with_uncovered_clover(tmp_path, fake_tool):
    repo_path = _fake_local_pest(tmp_path)
    fake_tool(
        pest_runner,
        respond=_write_reports(_read("junit-empty.xml"), _read("clover-uncovered.xml")),
    )

    result = PestRunner().run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["tests"]["total"] == 0
    assert result.raw_output["failures"] == []
    assert result.raw_output["coverage_percent"] == 0.0


def test_coverage_is_none_when_clover_file_missing(tmp_path, fake_tool):
    repo_path = _fake_local_pest(tmp_path)
    fake_tool(pest_runner, respond=_write_reports(_read("junit-pass.xml")))

    result = PestRunner().run(repo_path, exclude_paths=[])

    assert result.raw_output["tests"]["passed"] == 1
    assert result.raw_output["coverage_percent"] is None


@pytest.mark.parametrize("clover", ["", "<coverage><project"])
def test_coverage_is_none_when_clover_file_is_unparseable(tmp_path, fake_tool, clover):
    repo_path = _fake_local_pest(tmp_path)
    fake_tool(pest_runner, respond=_write_reports(_read("junit-pass.xml"), clover))

    result = PestRunner().run(repo_path, exclude_paths=[])

    assert result.raw_output["tests"]["passed"] == 1
    assert result.raw_output["coverage_percent"] is None


def test_coverage_is_none_when_clover_has_no_project_metrics(tmp_path, fake_tool):
    repo_path = _fake_local_pest(tmp_path)
    clover = '<?xml version="1.0"?><coverage><project name="x"/></coverage>'
    fake_tool(pest_runner, respond=_write_reports(_read("junit-pass.xml"), clover))

    result = PestRunner().run(repo_path, exclude_paths=[])

    assert result.raw_output["coverage_percent"] is None


def test_coverage_is_none_when_clover_counts_zero_statements(tmp_path, fake_tool):
    repo_path = _fake_local_pest(tmp_path)
    clover = _read("clover-pass.xml").replace('statements="1"', 'statements="0"')
    fake_tool(pest_runner, respond=_write_reports(_read("junit-pass.xml"), clover))

    result = PestRunner().run(repo_path, exclude_paths=[])

    assert result.raw_output["coverage_percent"] is None


def test_falls_back_when_junit_file_is_empty(tmp_path, fake_tool):
    repo_path = _fake_local_pest(tmp_path)
    fake_tool(pest_runner, returncode=2, respond=_write_reports(junit=""))

    result = PestRunner().run(repo_path, exclude_paths=[])

    assert result.exit_code == 2
    assert result.raw_output == {
        "tests": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
        "failures": [],
        "coverage_percent": None,
    }


def test_falls_back_when_junit_file_not_written(tmp_path, fake_tool):
    repo_path = _fake_local_pest(tmp_path)
    calls = fake_tool(pest_runner, returncode=255)

    result = PestRunner().run(repo_path, exclude_paths=[])

    assert result.exit_code == 255
    assert result.command == " ".join(calls[0])
    assert result.raw_output["tests"]["total"] == 0
    assert result.raw_output["coverage_percent"] is None
