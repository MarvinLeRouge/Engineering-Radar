import subprocess
from pathlib import Path

import pytest
from radar_audit.runners import pint_runner
from radar_audit.runners.pint_runner import PintRunner

from tests.git_helpers import init_git_repo


def _install_local_pint(repo_path):
    (repo_path / "composer.json").write_text(
        '{"name": "fixture/fixture", "require-dev": {"laravel/pint": "^1.0"}}\n'
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
def test_reports_pass_on_correctly_formatted_php(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": "<?php\n\nclass A {}\n"})
    _install_local_pint(repo_path)

    runner = PintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["result"] == "passed"


@pytest.mark.slow
def test_reports_pass_on_correctly_formatted_php_without_agent_env_vars(tmp_path, monkeypatch):
    # Pint silently switches its --format=json output to a different, agent-only
    # shape ({"tool": "pint", "result": ...}) when it detects known AI-coding-agent
    # env vars (CLAUDECODE, CLAUDE_CODE, AI_AGENT, ...). CI runners, and most real
    # shells, don't set these, so PintRunner must not depend on that agent-only
    # shape. Stripping the vars reproduces Pint's real --format=json output (the
    # native PHP-CS-Fixer reporter: {"about": ..., "files": [...], ...}).
    for var in ("CLAUDECODE", "CLAUDE_CODE", "AI_AGENT"):
        monkeypatch.delenv(var, raising=False)

    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": "<?php\n\nclass A {}\n"})
    _install_local_pint(repo_path)

    runner = PintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    # Confirms this actually exercised the native (non-agent) shape, not just a
    # value that happens to match in both shapes.
    assert "about" in result.raw_output
    assert result.raw_output["result"] == "passed"


@pytest.mark.slow
def test_reports_fail_on_badly_formatted_php(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": "<?php\nclass A{\npublic function f(){}\n}\n"})
    _install_local_pint(repo_path)

    runner = PintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    assert result.raw_output["result"] == "fail"


def test_reports_missing_binary_as_unusable(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": "<?php\n"})

    runner = PintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 127
    assert result.raw_output == {}


def test_reports_tool_identity():
    runner = PintRunner()

    assert runner.tool_name == "pint"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"php"})


_FIXTURES = Path(__file__).parent / "fixtures" / "runners" / "pint"


def _fake_local_pint(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": "<?php\n"})
    bin_path = repo_path / "vendor" / "bin" / "pint"
    bin_path.parent.mkdir(parents=True)
    bin_path.touch()
    return repo_path


def test_keeps_agent_shape_and_sets_passed_on_zero_exit(tmp_path, fake_tool):
    repo_path = _fake_local_pint(tmp_path)
    calls = fake_tool(pint_runner, stdout=(_FIXTURES / "agent-pass.json").read_text())

    result = PintRunner().run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {"tool": "pint", "result": "passed"}
    assert result.command == " ".join(calls[0])
    assert calls[0][1:] == ["--test", "--format=json"]


def test_sets_fail_and_keeps_files_on_nonzero_exit(tmp_path, fake_tool):
    repo_path = _fake_local_pint(tmp_path)
    fake_tool(pint_runner, stdout=(_FIXTURES / "agent-fail.json").read_text(), returncode=1)

    result = PintRunner().run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    assert result.raw_output["result"] == "fail"
    assert result.raw_output["files"][0]["path"] == "src/A.php"


def test_adds_result_to_native_shape_without_result_key(tmp_path, fake_tool):
    repo_path = _fake_local_pint(tmp_path)
    fake_tool(pint_runner, stdout=(_FIXTURES / "native-pass.json").read_text())

    result = PintRunner().run(repo_path, exclude_paths=[])

    assert result.raw_output["files"] == []
    assert "about" in result.raw_output
    assert result.raw_output["result"] == "passed"


def test_exit_code_overrides_self_reported_result(tmp_path, fake_tool):
    repo_path = _fake_local_pint(tmp_path)
    fake_tool(pint_runner, stdout='{"tool": "pint", "result": "passed"}', returncode=1)

    result = PintRunner().run(repo_path, exclude_paths=[])

    assert result.raw_output["result"] == "fail"


@pytest.mark.parametrize("stdout", ["PHP Fatal error: boom", "", "[1, 2]", "null"])
def test_keeps_raw_streams_when_stdout_is_not_a_json_object(tmp_path, fake_tool, stdout):
    repo_path = _fake_local_pint(tmp_path)
    fake_tool(pint_runner, stdout=stdout, stderr="trace", returncode=255)

    result = PintRunner().run(repo_path, exclude_paths=[])

    assert result.exit_code == 255
    assert result.raw_output == {"stdout": stdout, "stderr": "trace"}
