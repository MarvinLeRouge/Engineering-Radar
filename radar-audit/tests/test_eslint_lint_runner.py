# tests/test_eslint_lint_runner.py
import json
from pathlib import Path

import pytest
from radar_audit.runners import eslint_lint_runner
from radar_audit.runners.eslint_lint_runner import EslintLintRunner

from tests.git_helpers import init_git_repo


def _write_package_json(repo_path, lint_script):
    (repo_path / "package.json").write_text(
        json.dumps({"name": "fixture", "version": "1.0.0", "scripts": {"lint": lint_script}})
    )
    (repo_path / "eslint.config.js").write_text(
        'module.exports = [{ rules: { "no-unused-vars": "error" } }];\n'
    )


@pytest.mark.slow
def test_reports_no_violations_on_clean_js(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path, files={"src/a.js": "export function add(a, b) {\n  return a + b;\n}\n"}
    )
    _write_package_json(repo_path, "eslint src")

    runner = EslintLintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert all(entry["errorCount"] == 0 for entry in result.raw_output["results"])


@pytest.mark.slow
def test_reports_violations_on_unused_variable(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": "export function add(a, b) {\n  const unused = 1;\n  return a + b;\n}\n"
        },
    )
    _write_package_json(repo_path, "eslint src")

    runner = EslintLintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    flagged = [e for e in result.raw_output["results"] if e["errorCount"] > 0]
    assert len(flagged) == 1


@pytest.mark.slow
def test_reports_a_file_path_relative_to_target_path(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path, files={"src/a.js": "export function add(a, b) {\n  return a + b;\n}\n"}
    )
    _write_package_json(repo_path, "eslint src")

    runner = EslintLintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert any(e["filePath"] == "src/a.js" for e in result.raw_output["results"])


@pytest.mark.slow
def test_falls_back_to_target_path_when_no_lint_script(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path, files={"src/a.js": "export function add(a, b) {\n  return a + b;\n}\n"}
    )
    (repo_path / "package.json").write_text(json.dumps({"name": "fixture", "version": "1.0.0"}))
    (repo_path / "eslint.config.js").write_text("module.exports = [{}];\n")

    runner = EslintLintRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["results"]


@pytest.mark.slow
def test_excludes_paths_passed_via_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": "export function add(a, b) {\n  return a + b;\n}\n",
            "legacy/b.js": "const unused = 1;\n",
        },
    )
    _write_package_json(repo_path, "eslint src legacy")

    runner = EslintLintRunner()
    result = runner.run(repo_path, exclude_paths=[repo_path / "legacy"])

    flagged = [e for e in result.raw_output["results"] if e["errorCount"] > 0]
    assert len(flagged) == 0


@pytest.mark.slow
def test_scope_token_not_filtered_when_nested_path_excluded(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": "export function add(a, b) {\n  return a + b;\n}\n",
            "src/legacy/b.js": "const unused = 1;\n",
        },
    )
    _write_package_json(repo_path, "eslint src")

    runner = EslintLintRunner()
    result = runner.run(repo_path, exclude_paths=[repo_path / "src" / "legacy"])

    # Verify the clean file in src/ is still linted (src token not dropped)
    clean_files = [e for e in result.raw_output["results"] if e["errorCount"] == 0]
    assert any("a.js" in e["filePath"] for e in clean_files)
    # Verify the violation in src/legacy/ is still excluded
    flagged = [e for e in result.raw_output["results"] if e["errorCount"] > 0]
    assert len(flagged) == 0

    # Verify the command actually contains the "src" token (not dropped in favor of ".")
    # Split command string into tokens and check that "src" appears as a standalone arg
    command_tokens = result.command.split()
    assert "src" in command_tokens, (
        f"Scope token 'src' not found as standalone argument in command. "
        f"Command tokens: {command_tokens}"
    )
    # Verify that the bare "." fallback was NOT used
    assert "." not in command_tokens, (
        f"Bare '.' fallback should not be present when 'src' token is preserved. "
        f"Command tokens: {command_tokens}"
    )


def test_reports_tool_identity():
    runner = EslintLintRunner()

    assert runner.tool_name == "eslint"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})


# --- fast tests: ESLint is faked, outputs come from real captured runs ---

_FIXTURES = Path(__file__).parent / "fixtures" / "runners" / "eslint"


def _violation_stdout(target):
    return (_FIXTURES / "violation.json").read_text().replace("{target}", str(target))


def test_relativizes_file_paths_of_the_eslint_json_report(tmp_path, fake_tool):
    _write_package_json(tmp_path, "eslint src")
    (tmp_path / "src").mkdir()
    calls = fake_tool(eslint_lint_runner, stdout=_violation_stdout(tmp_path), returncode=1)

    result = EslintLintRunner().run(tmp_path, exclude_paths=[])

    assert calls == [["npx", "--package=eslint", "--", "eslint", "src", "--format", "json"]]
    assert result.command == "npx --package=eslint -- eslint src --format json"
    assert result.exit_code == 1
    (entry,) = result.raw_output["results"]
    assert entry["filePath"] == "src/a.js"
    assert entry["messages"][0]["ruleId"] == "no-unused-vars"
    assert entry["messages"][0]["line"] == 2


def test_falls_back_to_raw_output_when_eslint_stdout_is_not_json(tmp_path, fake_tool):
    fake_tool(eslint_lint_runner, stdout="Oops! Something went wrong", stderr="boom", returncode=2)

    result = EslintLintRunner().run(tmp_path, exclude_paths=[])

    assert result.raw_output == {"stdout": "Oops! Something went wrong", "stderr": "boom"}
    assert result.exit_code == 2


def test_lints_the_whole_target_when_there_is_no_package_json(tmp_path, fake_tool):
    calls = fake_tool(eslint_lint_runner, stdout="[]")

    result = EslintLintRunner().run(tmp_path, exclude_paths=[])

    assert calls[0][4:] == [".", "--format", "json"]
    assert result.raw_output == {"results": []}


def test_ignores_flags_and_missing_paths_of_the_lint_script(tmp_path, fake_tool):
    _write_package_json(tmp_path, "eslint --fix src missing.js tests")
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    calls = fake_tool(eslint_lint_runner, stdout="[]")

    EslintLintRunner().run(tmp_path, exclude_paths=[])

    assert calls[0][4:] == ["src", "tests", "--format", "json"]


def test_lints_the_whole_target_when_no_lint_script_path_exists(tmp_path, fake_tool):
    _write_package_json(tmp_path, "eslint missing")
    calls = fake_tool(eslint_lint_runner, stdout="[]")

    EslintLintRunner().run(tmp_path, exclude_paths=[])

    assert calls[0][4:] == [".", "--format", "json"]


def test_lints_the_whole_target_when_the_package_has_no_lint_script(tmp_path, fake_tool):
    (tmp_path / "package.json").write_text(json.dumps({"name": "fixture"}))
    calls = fake_tool(eslint_lint_runner, stdout="[]")

    EslintLintRunner().run(tmp_path, exclude_paths=[])

    assert calls[0][4:] == [".", "--format", "json"]


def test_drops_an_excluded_scope_token_and_keeps_the_others(tmp_path, fake_tool):
    _write_package_json(tmp_path, "eslint src tests")
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    calls = fake_tool(eslint_lint_runner, stdout="[]")

    EslintLintRunner().run(tmp_path, exclude_paths=[tmp_path / "tests"])

    assert calls[0] == [
        "npx",
        "--package=eslint",
        "--",
        "eslint",
        "src",
        "--format",
        "json",
        "--ignore-pattern",
        "tests/**",
    ]


def test_falls_back_to_the_whole_target_when_every_scope_token_is_excluded(tmp_path, fake_tool):
    _write_package_json(tmp_path, "eslint src")
    (tmp_path / "src").mkdir()
    calls = fake_tool(eslint_lint_runner, stdout="[]")

    EslintLintRunner().run(tmp_path, exclude_paths=[tmp_path / "src"])

    assert calls[0][4:] == [".", "--format", "json", "--ignore-pattern", "src/**"]


def test_skips_excluded_paths_outside_the_target(tmp_path, fake_tool):
    target = tmp_path / "repo"
    target.mkdir()
    calls = fake_tool(eslint_lint_runner, stdout="[]")

    EslintLintRunner().run(target, exclude_paths=[tmp_path / "elsewhere", target / "dist"])

    assert calls[0].count("--ignore-pattern") == 1
    assert calls[0][-1] == "dist/**"
