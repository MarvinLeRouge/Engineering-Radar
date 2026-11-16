import json
from pathlib import Path

import pytest
from radar_audit.runners import typescript_runner
from radar_audit.runners.typescript_runner import TypeScriptRunner

from tests.git_helpers import init_git_repo


def _write_package_json(repo_path, devDependencies=None):
    (repo_path / "package.json").write_text(
        json.dumps(
            {"name": "fixture", "version": "1.0.0", "devDependencies": devDependencies or {}}
        )
    )
    (repo_path / "tsconfig.json").write_text(
        json.dumps({"compilerOptions": {"strict": True, "noEmit": True}})
    )


@pytest.mark.slow
def test_reports_no_diagnostics_on_well_typed_code(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.ts": "export function add(a: number, b: number): number {\n  return a + b;\n}\n"
        },
    )
    _write_package_json(repo_path)

    runner = TypeScriptRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["diagnostics"] == []


@pytest.mark.slow
def test_reports_a_type_error(tmp_path):
    repo_path = tmp_path / "repo"
    code_with_error = (
        "export function add(a: number, b: number): number {\n  return a + b;\n}\nadd('x', 1);\n"
    )
    init_git_repo(repo_path, files={"src/a.ts": code_with_error})
    _write_package_json(repo_path)

    runner = TypeScriptRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    assert len(result.raw_output["diagnostics"]) >= 1


def test_skips_running_tsc_when_no_tsconfig_present(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path, files={"src/a.js": "export function add(a, b) {\n  return a + b;\n}\n"}
    )
    (repo_path / "package.json").write_text(json.dumps({"name": "fixture", "version": "1.0.0"}))

    runner = TypeScriptRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output == {"diagnostics": [], "total_files": 0}


def test_uses_typescript_package_when_vue_tsc_not_a_dev_dependency():
    runner = TypeScriptRunner()

    assert runner._resolve_package_and_binary({"devDependencies": {}}) == ("typescript", "tsc")


def test_uses_vue_tsc_package_when_declared_as_dev_dependency():
    runner = TypeScriptRunner()

    assert runner._resolve_package_and_binary({"devDependencies": {"vue-tsc": "^2.0.0"}}) == (
        "vue-tsc",
        "vue-tsc",
    )


def test_reports_tool_identity():
    runner = TypeScriptRunner()

    assert runner.tool_name == "tsc"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})


@pytest.mark.slow
def test_drops_diagnostics_of_excluded_files(tmp_path):
    repo_path = tmp_path / "repo"
    code_with_error = "export function add(a: number, b: number): number {\n  return a + b;\n}\n"
    init_git_repo(
        repo_path,
        files={
            "src/a.ts": code_with_error,
            "src/a.spec.ts": "import { add } from './a';\nadd('x', 1);\n",
        },
    )
    _write_package_json(repo_path)

    runner = TypeScriptRunner()
    result = runner.run(repo_path, exclude_paths=[(repo_path / "src" / "a.spec.ts").resolve()])

    assert result.raw_output["diagnostics"] == []
    assert result.raw_output["total_files"] == 1


_TSC_ERROR = (Path(__file__).parent / "fixtures" / "runners" / "tsc" / "type-error.txt").read_text()


def _ts_repo(tmp_path, devDependencies=None, files=None):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files=files or {"src/a.ts": "export const a = 1;\n", "src/b.vue": "<template/>\n"},
    )
    _write_package_json(repo_path, devDependencies)
    return repo_path


def test_parses_diagnostics_and_counts_source_files(tmp_path, fake_tool):
    repo_path = _ts_repo(tmp_path)
    calls = fake_tool(typescript_runner, stdout=_TSC_ERROR, returncode=1)

    result = TypeScriptRunner().run(repo_path, exclude_paths=[])

    assert result.exit_code == 1
    assert result.command == "npx --package=typescript -- tsc --noEmit"
    assert calls == [["npx", "--package=typescript", "--", "tsc", "--noEmit"]]
    assert result.raw_output["diagnostics"] == [
        {
            "file": "src/a.ts",
            "line": 4,
            "column": 5,
            "code": "TS2345",
            "message": "Argument of type 'string' is not assignable to parameter of type 'number'.",
        }
    ]
    assert result.raw_output["total_files"] == 2


def test_uses_vue_tsc_command_when_declared(tmp_path, fake_tool):
    repo_path = _ts_repo(tmp_path, {"vue-tsc": "^2.0.0"})
    calls = fake_tool(typescript_runner)

    result = TypeScriptRunner().run(repo_path, exclude_paths=[])

    assert calls[0] == ["npx", "--package=vue-tsc", "--", "vue-tsc", "--noEmit"]
    assert result.raw_output["diagnostics"] == []


def test_defaults_to_typescript_when_package_json_missing(tmp_path, fake_tool):
    repo_path = _ts_repo(tmp_path)
    (repo_path / "package.json").unlink()
    calls = fake_tool(typescript_runner)

    TypeScriptRunner().run(repo_path, exclude_paths=[])

    assert calls[0][1:3] == ["--package=typescript", "--"]


def test_ignores_non_diagnostic_lines(tmp_path, fake_tool):
    repo_path = _ts_repo(tmp_path)
    stdout = "Found 1 error.\n  continuation line\n" + _TSC_ERROR
    fake_tool(typescript_runner, stdout=stdout, returncode=1)

    result = TypeScriptRunner().run(repo_path, exclude_paths=[])

    assert [d["file"] for d in result.raw_output["diagnostics"]] == ["src/a.ts"]


def test_drops_excluded_and_skipped_directory_diagnostics(tmp_path, fake_tool):
    repo_path = _ts_repo(
        tmp_path,
        files={"src/a.ts": "x\n", "src/a.spec.ts": "x\n", "dist/out.ts": "x\n"},
    )
    error = _TSC_ERROR.strip()
    stdout = "\n".join(
        [
            error.replace("src/a.ts", "src/a.spec.ts"),
            error.replace("src/a.ts", "dist/out.ts"),
            error,
        ]
    )
    fake_tool(typescript_runner, stdout=stdout, returncode=1)

    result = TypeScriptRunner().run(repo_path, exclude_paths=[repo_path / "src" / "a.spec.ts"])

    assert [d["file"] for d in result.raw_output["diagnostics"]] == ["src/a.ts"]
    assert result.raw_output["total_files"] == 1
