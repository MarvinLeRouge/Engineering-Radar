from radar_audit.runners.docvet_runner import DocvetRunner
from radar_audit.scope import out_of_scope_paths

from tests.git_helpers import init_git_repo

_FULLY_DOCUMENTED_MODULE = (
    '"""Module docstring."""\n\ndef add(a, b):\n    """Add two numbers."""\n    return a + b\n'
)

_PARTIALLY_DOCUMENTED_MODULE = (
    "def add(a, b):\n"
    '    """Add two numbers."""\n'
    "    return a + b\n"
    "\n"
    "def subtract(a, b):\n"
    "    return a - b\n"
)


def test_reports_full_coverage_on_a_fully_documented_module(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": _FULLY_DOCUMENTED_MODULE})

    runner = DocvetRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["presence_coverage"]["percentage"] == 100.0


def test_reports_partial_coverage_and_a_finding_on_an_undocumented_function(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": _PARTIALLY_DOCUMENTED_MODULE})

    runner = DocvetRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["presence_coverage"]["percentage"] < 100.0
    assert any(f["symbol"] == "subtract" for f in result.raw_output["findings"])


def test_reports_a_file_path_relative_to_target_path(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": _PARTIALLY_DOCUMENTED_MODULE})

    runner = DocvetRunner()
    result = runner.run(repo_path / "src", exclude_paths=[])

    findings = result.raw_output["findings"]
    assert any(f["file"] == "a.py" for f in findings)


def test_excludes_paths_passed_via_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.py": _FULLY_DOCUMENTED_MODULE,
            "src/excluded/b.py": _PARTIALLY_DOCUMENTED_MODULE,
        },
    )

    runner = DocvetRunner()
    result = runner.run(repo_path / "src", exclude_paths=[repo_path / "src" / "excluded"])

    findings = result.raw_output.get("findings", [])
    assert not any("excluded" in f["file"] for f in findings)


def test_excludes_nested_paths_more_than_one_level_deep(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.py": _FULLY_DOCUMENTED_MODULE,
            "src/apps/web/lib/y.py": _PARTIALLY_DOCUMENTED_MODULE,
        },
    )

    runner = DocvetRunner()
    result = runner.run(repo_path / "src", exclude_paths=[repo_path / "src" / "apps" / "web"])

    assert result.raw_output["presence_coverage"]["percentage"] == 100.0
    findings = result.raw_output.get("findings", [])
    assert not any("apps/web" in f["file"] for f in findings)


def test_excludes_scripts_by_default_and_tests_through_the_audit_scope(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/a.py": _FULLY_DOCUMENTED_MODULE,
            "src/tests/test_a.py": _PARTIALLY_DOCUMENTED_MODULE,
            "src/scripts/tool.py": _PARTIALLY_DOCUMENTED_MODULE,
            "src/excluded/b.py": _PARTIALLY_DOCUMENTED_MODULE,
        },
    )

    runner = DocvetRunner()
    src = repo_path / "src"
    # Tests reach docvet through the audit scope (radar_audit.scope), as in execute_audit.
    exclude_paths = [src / "excluded", *out_of_scope_paths(src, runner.excluded_zones)]
    result = runner.run(src, exclude_paths=exclude_paths)

    assert result.raw_output["presence_coverage"]["percentage"] == 100.0
    assert result.raw_output.get("findings", []) == []


def test_falls_back_to_stdout_when_no_python_files_remain(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": _FULLY_DOCUMENTED_MODULE})

    runner = DocvetRunner()
    result = runner.run(repo_path / "src", exclude_paths=[repo_path / "src"])

    assert "presence_coverage" not in result.raw_output


def test_reports_tool_identity():
    runner = DocvetRunner()

    assert runner.tool_name == "docvet"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"python"})
