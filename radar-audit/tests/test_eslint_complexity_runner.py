import json
from pathlib import Path

import pytest
from radar_audit.runners import eslint_complexity_runner
from radar_audit.runners.eslint_complexity_runner import EslintComplexityRunner

from tests.git_helpers import init_git_repo

_SIMPLE_FUNCTION = "export function add(a, b) {\n  return a + b;\n}\n"

_COMPLEX_FUNCTION = (
    "export function classify(n) {\n"
    + "".join(f"  if (n === {i}) return {i};\n" for i in range(15))
    + "  return -1;\n}\n"
)


def _write_package_json(repo_path, esm_type=False):
    config = {"name": "fixture", "version": "1.0.0"}
    if esm_type:
        config["type"] = "module"
    (repo_path / "package.json").write_text(json.dumps(config))


@pytest.mark.slow
def test_reports_low_complexity_on_a_simple_function(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.js": _SIMPLE_FUNCTION})
    _write_package_json(repo_path)

    runner = EslintComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    complexities = [c["complexity"] for c in result.raw_output["complexities"]]
    assert complexities and max(complexities) <= 2


@pytest.mark.slow
def test_reports_a_file_path_relative_to_target_path(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.js": _SIMPLE_FUNCTION})
    _write_package_json(repo_path)

    runner = EslintComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert any(c["file"] == "src/a.js" for c in result.raw_output["complexities"])


@pytest.mark.slow
def test_reports_high_complexity_on_a_branchy_function(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.js": _COMPLEX_FUNCTION})
    _write_package_json(repo_path)

    runner = EslintComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    complexities = [c["complexity"] for c in result.raw_output["complexities"]]
    assert complexities and max(complexities) >= 11


def test_reports_tool_identity():
    runner = EslintComplexityRunner()

    assert runner.tool_name == "eslint-complexity"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})


@pytest.mark.slow
def test_excludes_paths_passed_via_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": _SIMPLE_FUNCTION,
            "src/excluded/b.js": _COMPLEX_FUNCTION,
        },
    )
    _write_package_json(repo_path)

    runner = EslintComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[repo_path / "src" / "excluded"])

    # Verify that the excluded file's violations are not in the output
    complexities = result.raw_output["complexities"]
    excluded_files = [c["file"] for c in complexities]
    assert not any("excluded" in f for f in excluded_files)

    # Verify that non-excluded violations are present (not over-broad exclusion)
    assert any("src/a.js" in f or "a.js" in f for f in excluded_files)


@pytest.mark.slow
def test_always_excludes_dist_directory_regardless_of_exclude_paths(tmp_path):
    repo_path = tmp_path / "test_repo_for_build_check"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": _SIMPLE_FUNCTION,
            "dist/bundle.js": _COMPLEX_FUNCTION,
        },
    )
    _write_package_json(repo_path)

    runner = EslintComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    complexities = result.raw_output["complexities"]
    excluded_files = [c["file"] for c in complexities]
    # bundle.js from dist/ should be excluded
    assert not any("bundle.js" in f for f in excluded_files), "dist/bundle.js should be excluded"
    # a.js from src/ should still be checked
    assert any("a.js" in f for f in excluded_files), "src/a.js should not be excluded"


@pytest.mark.slow
def test_always_excludes_vendor_directory_regardless_of_exclude_paths(tmp_path):
    repo_path = tmp_path / "test_repo_for_vendor_check"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": _SIMPLE_FUNCTION,
            "vendor/bundle.js": _COMPLEX_FUNCTION,
        },
    )
    _write_package_json(repo_path)

    runner = EslintComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    complexities = result.raw_output["complexities"]
    excluded_files = [c["file"] for c in complexities]
    # bundle.js from vendor/ should be excluded
    assert not any("bundle.js" in f for f in excluded_files), "vendor/bundle.js should be excluded"
    # a.js from src/ should still be checked
    assert any("a.js" in f for f in excluded_files), "src/a.js should not be excluded"


@pytest.mark.slow
def test_always_excludes_a_nested_vendor_directory(tmp_path):
    repo_path = tmp_path / "test_repo_for_nested_vendor_check"
    init_git_repo(
        repo_path,
        files={
            "src/a.js": _SIMPLE_FUNCTION,
            "backend/vendor/pkg/bundle.js": _COMPLEX_FUNCTION,
        },
    )
    _write_package_json(repo_path)

    runner = EslintComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    complexities = result.raw_output["complexities"]
    excluded_files = [c["file"] for c in complexities]
    assert not any("bundle.js" in f for f in excluded_files), (
        "backend/vendor/pkg/bundle.js should be excluded"
    )
    assert any("a.js" in f for f in excluded_files), "src/a.js should not be excluded"


@pytest.mark.slow
def test_does_not_exclude_a_directory_whose_name_merely_contains_vendor(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={"vendors-config/a.js": _COMPLEX_FUNCTION},
    )
    _write_package_json(repo_path)

    runner = EslintComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    complexities = result.raw_output["complexities"]
    flagged_files = [c["file"] for c in complexities]
    assert any("a.js" in f for f in flagged_files), (
        "vendors-config/a.js should not be excluded (not a real vendor/ segment)"
    )


@pytest.mark.slow
def test_runs_successfully_on_esm_type_targets(tmp_path):
    """Regression test: ensure runner survives targets with package.json "type": "module"."""
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.js": _COMPLEX_FUNCTION})
    _write_package_json(repo_path, esm_type=True)

    runner = EslintComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    # The critical assertion: complexities key must be present and non-empty.
    # Before the fix, this would silently return {"stdout": "", "stderr": ...}
    # with no "complexities" key at all.
    assert "complexities" in result.raw_output
    complexities = result.raw_output["complexities"]
    assert complexities and max(c["complexity"] for c in complexities) >= 11


# --- fast tests: ESLint is faked, outputs come from real captured runs ---

_FIXTURE = Path(__file__).parent / "fixtures" / "runners" / "eslint-complexity" / "complexity.json"


def _complexity_stdout(target):
    return _FIXTURE.read_text().replace("{target}", str(target))


def test_extracts_each_function_complexity_with_a_relative_path(tmp_path, fake_tool):
    calls = fake_tool(eslint_complexity_runner, stdout=_complexity_stdout(tmp_path), returncode=1)

    result = EslintComplexityRunner().run(tmp_path, exclude_paths=[])

    assert result.raw_output == {
        "complexities": [
            {"file": "src/a.js", "line": 1, "name": "Function 'classify'", "complexity": 16}
        ]
    }
    assert result.exit_code == 1
    assert result.command == " ".join(calls[0])


def test_passes_the_audit_config_and_always_excluded_dirs(tmp_path, fake_tool):
    seen = {}

    def respond(command, cwd):
        config = Path(command[command.index("-c") + 1])
        seen["config"] = config
        seen["content"] = config.read_text()
        seen["cwd"] = cwd

    calls = fake_tool(eslint_complexity_runner, stdout="[]", respond=respond)

    EslintComplexityRunner().run(tmp_path, exclude_paths=[])

    command = calls[0]
    assert command[:4] == ["npx", "--package=eslint", "--", "eslint"]
    assert command[6] == str(tmp_path)
    assert command[7:9] == ["--format", "json"]
    patterns = [command[i + 1] for i, a in enumerate(command) if a == "--ignore-pattern"]
    assert patterns == ["**/node_modules/**", "**/vendor/**", "**/dist/**", "**/build/**"]
    assert 'complexity: ["error", 0]' in seen["content"]
    assert seen["config"].parent == tmp_path
    assert seen["cwd"] == tmp_path
    assert not seen["config"].exists()


def test_removes_the_temporary_config_even_when_the_tool_raises(tmp_path, fake_tool):
    def respond(command, cwd):
        raise RuntimeError("npx crashed")

    fake_tool(eslint_complexity_runner, respond=respond)

    with pytest.raises(RuntimeError):
        EslintComplexityRunner().run(tmp_path, exclude_paths=[])

    assert list(tmp_path.glob("*.config.cjs")) == []


def test_translates_excluded_directories_and_files_into_ignore_patterns(tmp_path, fake_tool):
    (tmp_path / "tests").mkdir()
    (tmp_path / "gen.js").write_text("")
    calls = fake_tool(eslint_complexity_runner, stdout="[]")

    EslintComplexityRunner().run(
        tmp_path,
        exclude_paths=[tmp_path / "tests", tmp_path / "gen.js", tmp_path.parent / "outside"],
    )

    patterns = [calls[0][i + 1] for i, a in enumerate(calls[0]) if a == "--ignore-pattern"]
    assert patterns[4:] == ["tests/**", "gen.js"]


def test_falls_back_to_raw_output_when_eslint_stdout_is_not_json(tmp_path, fake_tool):
    fake_tool(eslint_complexity_runner, stdout="not json", stderr="crash", returncode=2)

    result = EslintComplexityRunner().run(tmp_path, exclude_paths=[])

    assert result.raw_output == {"stdout": "not json", "stderr": "crash"}
    assert result.exit_code == 2
    assert list(tmp_path.glob("*.config.cjs")) == []


def test_ignores_messages_that_are_not_complexity_reports(tmp_path, fake_tool):
    report = [
        {
            "filePath": str(tmp_path / "src" / "a.js"),
            "messages": [
                {"message": "Parsing error: Unexpected token", "line": 3},
                {"line": 4},
                {"message": "Method 'run' has a complexity of 3. Maximum allowed is 0.", "line": 7},
            ],
        },
        {"filePath": str(tmp_path / "src" / "b.js")},
    ]
    fake_tool(eslint_complexity_runner, stdout=json.dumps(report))

    result = EslintComplexityRunner().run(tmp_path, exclude_paths=[])

    assert result.raw_output == {
        "complexities": [{"file": "src/a.js", "line": 7, "name": "Method 'run'", "complexity": 3}]
    }
