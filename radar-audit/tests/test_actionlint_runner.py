from radar_audit.runners.actionlint_runner import ActionlintRunner

from tests.git_helpers import init_git_repo

_CLEAN_WORKFLOW = """\
name: CI
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "hello"
"""

_DIRTY_WORKFLOW = """\
name: CI
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo $FOO
"""


def test_reports_no_findings_for_a_clean_workflow(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={".github/workflows/ci.yml": _CLEAN_WORKFLOW})

    runner = ActionlintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {"findings": []}


def test_reports_a_shellcheck_finding_for_an_unquoted_variable(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={".github/workflows/ci.yml": _DIRTY_WORKFLOW})

    runner = ActionlintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    findings = result.raw_output["findings"]
    assert len(findings) == 1
    assert findings[0]["kind"] == "shellcheck"
    assert findings[0]["filepath"] == ".github/workflows/ci.yml"


def test_reports_an_error_payload_when_no_workflows_directory_exists(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"a.txt": "x\n"})

    runner = ActionlintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 3
    assert "error" in result.raw_output
    assert "findings" not in result.raw_output


def test_reports_tool_identity():
    runner = ActionlintRunner()

    assert runner.tool_name == "actionlint"
    assert runner.scope == "repo"
    assert runner.supported_stacks == frozenset()
