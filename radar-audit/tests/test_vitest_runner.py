import json
import subprocess
from pathlib import Path

import pytest
from radar_audit.runners import vitest_runner
from radar_audit.runners.vitest_runner import VitestRunner

from tests.git_helpers import init_git_repo


def _install_local_vitest(repo_path, with_coverage=True):
    dev_deps = '"vitest": "^3.2.7"'
    if with_coverage:
        dev_deps += ', "@vitest/coverage-v8": "^3.2.7"'
    (repo_path / "package.json").write_text(
        '{"name": "fixture", "version": "1.0.0", "type": "module", '
        '"devDependencies": {' + dev_deps + "}}\n"
    )
    subprocess.run(
        ["npm", "install", "--no-audit", "--no-fund"],
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
            "src/add.js": "export function add(a, b) { return a + b; }\n",
            "src/add.test.js": (
                'import { expect, test } from "vitest";\n'
                'import { add } from "./add.js";\n\n'
                'test("adds", () => { expect(add(1, 2)).toBe(3); });\n'
            ),
        },
    )
    _install_local_vitest(repo_path)

    runner = VitestRunner()
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
            "src/add.js": "export function add(a, b) { return a + b; }\n",
            "src/add.test.js": (
                'import { expect, test } from "vitest";\n'
                'import { add } from "./add.js";\n\n'
                'test("adds", () => { expect(add(1, 2)).toBe(4); });\n'
            ),
        },
    )
    _install_local_vitest(repo_path)

    runner = VitestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    assert result.raw_output["tests"]["failed"] == 1
    failures = result.raw_output["failures"]
    assert len(failures) == 1
    assert failures[0]["file"] == "src/add.test.js"


@pytest.mark.slow
def test_reports_no_coverage_percent_when_provider_absent(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/add.js": "export function add(a, b) { return a + b; }\n",
            "src/add.test.js": (
                'import { expect, test } from "vitest";\n'
                'import { add } from "./add.js";\n\n'
                'test("adds", () => { expect(add(1, 2)).toBe(3); });\n'
            ),
        },
    )
    _install_local_vitest(repo_path, with_coverage=False)

    runner = VitestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["coverage_percent"] is None


@pytest.mark.slow
def test_excludes_a_nested_worktree_from_test_discovery(tmp_path):
    # Real-world shape found auditing Summit-Stats: a `.claude/worktrees/<branch>/`
    # git worktree checked out inside the repo carries its own copy of the test
    # suite (plus, in that case, stale Playwright .spec.js files that don't parse
    # as Vitest tests at all) -- Vitest's default glob recurses the whole tree and
    # picks it up a second time unless exclude_paths is forwarded as --exclude.
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/add.js": "export function add(a, b) { return a + b; }\n",
            "src/add.test.js": (
                'import { expect, test } from "vitest";\n'
                'import { add } from "./add.js";\n\n'
                'test("adds", () => { expect(add(1, 2)).toBe(3); });\n'
            ),
            "nested-worktree/src/add.test.js": (
                'import { expect, test } from "vitest";\n\n'
                'test("duplicate", () => { expect(1).toBe(1); });\n'
            ),
        },
    )
    _install_local_vitest(repo_path)

    runner = VitestRunner()
    excluded_path = repo_path / "nested-worktree"

    result_without_exclude = runner.run(repo_path, exclude_paths=[])
    result_with_exclude = runner.run(repo_path, exclude_paths=[excluded_path])

    assert result_without_exclude.raw_output["tests"]["total"] == 2
    assert result_with_exclude.raw_output["tests"]["total"] == 1


def test_reports_missing_binary_as_unusable(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/add.js": "export function add() {}\n"})

    runner = VitestRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 127
    assert result.raw_output == {}


def test_reports_tool_identity():
    runner = VitestRunner()

    assert runner.tool_name == "vitest"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})


_FIXTURES = Path(__file__).parent / "fixtures" / "runners" / "vitest"


def _fixture(name, repo_path):
    return (_FIXTURES / name).read_text().replace("{target}", str(repo_path))


def _fake_local_vitest(tmp_path, with_coverage=True):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/add.js": "export function add() {}\n"})
    bin_path = repo_path / "node_modules" / ".bin" / "vitest"
    bin_path.parent.mkdir(parents=True)
    bin_path.touch()
    if with_coverage:
        (repo_path / "node_modules" / "@vitest" / "coverage-v8").mkdir(parents=True)
    return repo_path


def _flag_value(command, prefix):
    return next(Path(arg.removeprefix(prefix)) for arg in command if arg.startswith(prefix))


def _responder(report=None, summary=None):
    def respond(command, cwd):
        if report is not None:
            _flag_value(command, "--outputFile=").write_text(report)
        reports_dir = next(
            (a for a in command if a.startswith("--coverage.reportsDirectory=")), None
        )
        if summary is not None and reports_dir is not None:
            directory = Path(reports_dir.split("=", 1)[1])
            directory.mkdir(parents=True)
            (directory / "coverage-summary.json").write_text(summary)

    return respond


def test_parses_passing_report_and_coverage_percent(tmp_path, fake_tool):
    repo_path = _fake_local_vitest(tmp_path)
    summary = (_FIXTURES / "coverage-summary.json").read_text()
    calls = fake_tool(
        vitest_runner,
        returncode=0,
        respond=_responder(_fixture("report-pass.json", repo_path), summary),
    )

    result = VitestRunner().run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {
        "tests": {"total": 1, "passed": 1, "failed": 0, "skipped": 0},
        "failures": [],
        "coverage_percent": 100,
    }
    assert result.command == " ".join(calls[0])
    assert "--coverage" in calls[0]
    assert "--coverage.reporter=json-summary" in calls[0]


def test_relativizes_failure_file_and_keeps_name(tmp_path, fake_tool):
    repo_path = _fake_local_vitest(tmp_path)
    fake_tool(
        vitest_runner,
        returncode=1,
        respond=_responder(_fixture("report-fail.json", repo_path)),
    )

    result = VitestRunner().run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    assert result.raw_output["tests"] == {"total": 1, "passed": 0, "failed": 1, "skipped": 0}
    assert result.raw_output["failures"] == [
        {"file": "src/add.test.js", "name": "adds", "line": None}
    ]
    assert result.raw_output["coverage_percent"] is None


def test_failure_name_falls_back_to_title_when_full_name_missing(tmp_path, fake_tool):
    repo_path = _fake_local_vitest(tmp_path, with_coverage=False)
    report = json.loads(_fixture("report-fail.json", repo_path))
    del report["testResults"][0]["assertionResults"][0]["fullName"]
    fake_tool(vitest_runner, returncode=1, respond=_responder(json.dumps(report)))

    result = VitestRunner().run(repo_path, exclude_paths=[])

    assert result.raw_output["failures"][0]["name"] == "adds"


def test_omits_coverage_flags_when_provider_absent(tmp_path, fake_tool):
    repo_path = _fake_local_vitest(tmp_path, with_coverage=False)
    calls = fake_tool(
        vitest_runner,
        respond=_responder(_fixture("report-pass.json", repo_path)),
    )

    result = VitestRunner().run(repo_path, exclude_paths=[])

    assert not any(arg.startswith("--coverage") for arg in calls[0])
    assert result.raw_output["coverage_percent"] is None
    assert result.raw_output["tests"]["passed"] == 1


def test_coverage_is_none_when_summary_file_missing(tmp_path, fake_tool):
    repo_path = _fake_local_vitest(tmp_path)
    fake_tool(
        vitest_runner,
        respond=_responder(_fixture("report-pass.json", repo_path)),
    )

    result = VitestRunner().run(repo_path, exclude_paths=[])

    assert result.raw_output["coverage_percent"] is None


def test_forwards_only_in_tree_exclude_paths_as_globs(tmp_path, fake_tool):
    repo_path = _fake_local_vitest(tmp_path, with_coverage=False)
    calls = fake_tool(
        vitest_runner,
        respond=_responder(_fixture("report-pass.json", repo_path)),
    )

    VitestRunner().run(
        repo_path, exclude_paths=[repo_path / "nested-worktree", tmp_path / "elsewhere"]
    )

    command = calls[0]
    assert command.count("--exclude") == 1
    assert command[command.index("--exclude") + 1] == "nested-worktree/**"


def test_returns_zero_test_fallback_when_no_report_written(tmp_path, fake_tool):
    repo_path = _fake_local_vitest(tmp_path)
    calls = fake_tool(vitest_runner, returncode=1, stderr="boom")

    result = VitestRunner().run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    assert result.command == " ".join(calls[0])
    assert result.raw_output == {
        "tests": {"total": 0, "passed": 0, "failed": 0, "skipped": 0},
        "failures": [],
        "coverage_percent": None,
    }
