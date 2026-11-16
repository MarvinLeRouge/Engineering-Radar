import json
from pathlib import Path

import pytest
from radar_audit.runners import knip_runner
from radar_audit.runners.knip_runner import KnipRunner

from tests.git_helpers import init_git_repo

_USED_HELPER = "export function used() {\n  return 1;\n}\n"

_HELPER_WITH_UNUSED_EXPORT = (
    "export function used() {\n  return 1;\n}\n\nexport function unusedExport() {\n  return 2;\n}\n"
)

_MAIN_JS = 'import { used } from "./helpers.js";\nconsole.log(used());\n'

_INDEX_HTML = (
    "<!doctype html>\n<html><body>"
    '<script type="module" src="/src/main.js"></script>'
    "</body></html>\n"
)


def _write_package_json(repo_path):
    (repo_path / "package.json").write_text(json.dumps({"name": "fixture", "type": "module"}))


@pytest.mark.slow
def test_reports_no_issues_when_all_exports_are_used(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "index.html": _INDEX_HTML,
            "src/main.js": _MAIN_JS,
            "src/helpers.js": _USED_HELPER,
        },
    )
    _write_package_json(repo_path)

    runner = KnipRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["issues"] == []


@pytest.mark.slow
def test_reports_an_unused_export(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "index.html": _INDEX_HTML,
            "src/main.js": _MAIN_JS,
            "src/helpers.js": _HELPER_WITH_UNUSED_EXPORT,
        },
    )
    _write_package_json(repo_path)

    runner = KnipRunner()
    result = runner.run(repo_path, exclude_paths=[])

    issues = result.raw_output["issues"]
    exported_names = {e["name"] for issue in issues for e in issue.get("exports", [])}
    assert "unusedExport" in exported_names


@pytest.mark.slow
def test_excludes_paths_passed_via_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "index.html": _INDEX_HTML,
            "src/main.js": _MAIN_JS,
            "src/helpers.js": _USED_HELPER,
            "excluded/nested/orphan.js": _HELPER_WITH_UNUSED_EXPORT,
        },
    )
    _write_package_json(repo_path)

    runner = KnipRunner()
    result = runner.run(repo_path, exclude_paths=[repo_path / "excluded"])

    issues = result.raw_output["issues"]
    reported_files = {issue["file"] for issue in issues}
    reported_files |= {f["name"] for issue in issues for f in issue.get("files", [])}
    assert not any(name.startswith("excluded") for name in reported_files)


@pytest.mark.slow
def test_reports_the_orphan_file_when_it_is_not_excluded(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "index.html": _INDEX_HTML,
            "src/main.js": _MAIN_JS,
            "src/helpers.js": _USED_HELPER,
            "excluded/nested/orphan.js": _HELPER_WITH_UNUSED_EXPORT,
        },
    )
    _write_package_json(repo_path)

    runner = KnipRunner()
    result = runner.run(repo_path, exclude_paths=[])

    issues = result.raw_output["issues"]
    reported_files = {f["name"] for issue in issues for f in issue.get("files", [])}
    assert "excluded/nested/orphan.js" in reported_files


def test_returns_an_unusable_payload_when_no_entry_point_candidate_exists(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/helpers.js": _USED_HELPER})
    _write_package_json(repo_path)

    runner = KnipRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert "issues" not in result.raw_output
    assert result.raw_output == {"stdout": "", "stderr": "no entry point candidate found"}


def test_reports_tool_identity():
    runner = KnipRunner()

    assert runner.tool_name == "knip"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"javascript"})


# --- fast tests: knip is faked, output comes from a real captured run ---

_FIXTURE = Path(__file__).parent / "fixtures" / "runners" / "knip" / "unused-export.json"


def _config_written_for(command, cwd):
    return json.loads((cwd / command[command.index("--config") + 1]).read_text())


def _run_with_main_js(tmp_path, fake_tool, **tool):
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "main.js").write_text(_MAIN_JS)
    return fake_tool(knip_runner, **tool)


def test_parses_the_knip_json_report(tmp_path, fake_tool):
    calls = _run_with_main_js(tmp_path, fake_tool, stdout=_FIXTURE.read_text(), returncode=1)

    result = KnipRunner().run(tmp_path, exclude_paths=[])

    (issue,) = result.raw_output["issues"]
    assert issue["file"] == "src/helpers.js"
    assert issue["exports"][0]["name"] == "unusedExport"
    assert result.exit_code == 1
    assert result.command == " ".join(calls[0])
    assert calls[0][:4] == ["npx", "--package=knip", "--", "knip"]
    assert calls[0][-2:] == ["--reporter", "json"]


def test_writes_a_temporary_config_with_entries_and_ignores_then_removes_it(tmp_path, fake_tool):
    (tmp_path / "index.html").write_text(_INDEX_HTML)
    (tmp_path / "dist").mkdir()
    (tmp_path / "gen.js").write_text("")
    configs = []

    def respond(command, cwd):
        configs.append(_config_written_for(command, cwd))

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.js").write_text(_MAIN_JS)
    calls = fake_tool(knip_runner, stdout='{"issues":[]}', respond=respond)

    KnipRunner().run(
        tmp_path,
        exclude_paths=[tmp_path / "dist", tmp_path / "gen.js", tmp_path, tmp_path.parent / "out"],
    )

    assert configs == [
        {"entry": ["index.html", "src/main.js"], "ignore": ["dist/**", "gen.js", "**"]}
    ]
    assert not Path(calls[0][calls[0].index("--config") + 1]).exists()


def test_removes_the_temporary_config_even_when_the_tool_raises(tmp_path, fake_tool):
    def respond(command, cwd):
        raise RuntimeError("npx crashed")

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.js").write_text(_MAIN_JS)
    calls = fake_tool(knip_runner, respond=respond)

    with pytest.raises(RuntimeError):
        KnipRunner().run(tmp_path, exclude_paths=[])

    assert not Path(calls[0][calls[0].index("--config") + 1]).exists()


def test_parses_json_preceded_by_tool_noise(tmp_path, fake_tool):
    _run_with_main_js(
        tmp_path, fake_tool, stdout='npm warn exec something\n{"issues":[]}\n', returncode=0
    )

    result = KnipRunner().run(tmp_path, exclude_paths=[])

    assert result.raw_output == {"issues": []}


def test_falls_back_to_raw_output_when_stdout_has_no_issues_prefix(tmp_path, fake_tool):
    _run_with_main_js(tmp_path, fake_tool, stdout="boom", stderr="err", returncode=2)

    result = KnipRunner().run(tmp_path, exclude_paths=[])

    assert result.raw_output == {"stdout": "boom", "stderr": "err"}
    assert result.exit_code == 2


def test_falls_back_to_raw_output_when_the_json_is_truncated(tmp_path, fake_tool):
    truncated = _FIXTURE.read_text()[:40]
    _run_with_main_js(tmp_path, fake_tool, stdout=truncated, stderr="cut", returncode=1)

    result = KnipRunner().run(tmp_path, exclude_paths=[])

    assert result.raw_output == {"stdout": truncated, "stderr": "cut"}
