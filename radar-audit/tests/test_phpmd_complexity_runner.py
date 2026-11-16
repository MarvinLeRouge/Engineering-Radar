from pathlib import Path

import pytest
from radar_audit.runners import phpmd_complexity_runner
from radar_audit.runners.phpmd_complexity_runner import PhpmdComplexityRunner

from tests.git_helpers import init_git_repo

_SIMPLE_METHOD = (
    "<?php\n\nclass A\n{\n    public function add(int $a, int $b): int\n"
    "    {\n        return $a + $b;\n    }\n}\n"
)

_COMPLEX_METHOD_BODY = "".join(f"        if ($n === {i}) return {i};\n" for i in range(15))
_COMPLEX_METHOD = (
    "<?php\n\nclass A\n{\n    public function classify(int $n): int\n    {\n"
    + _COMPLEX_METHOD_BODY
    + "        return -1;\n    }\n}\n"
)

_UNUSED_VARIABLE_METHOD = (
    "<?php\n\nclass A\n{\n    public function compute(): int\n    {\n"
    "        $unused = 42;\n        return 1;\n    }\n}\n"
)


@pytest.mark.slow
def test_reports_no_violations_on_a_simple_method(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": _SIMPLE_METHOD})

    runner = PhpmdComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.raw_output["violations"] == []


@pytest.mark.slow
def test_reports_high_complexity_on_a_branchy_method(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": _COMPLEX_METHOD})

    runner = PhpmdComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    violations = result.raw_output["violations"]
    assert violations and max(v["complexity"] for v in violations) >= 11


@pytest.mark.slow
def test_reports_a_file_path_relative_to_target_path(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": _COMPLEX_METHOD})

    runner = PhpmdComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    violations = result.raw_output["violations"]
    assert any(v["file"] == "src/A.php" for v in violations)


@pytest.mark.slow
def test_excludes_paths_passed_via_exclude_paths(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/A.php": _COMPLEX_METHOD,
            "src/excluded/B.php": _COMPLEX_METHOD,
        },
    )

    runner = PhpmdComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[repo_path / "src" / "excluded"])

    violations = result.raw_output["violations"]

    # Verify that the excluded file's violations are not in the output
    excluded_files = [v["file"] for v in violations if "excluded" in v["file"]]
    assert len(excluded_files) == 0, "Excluded directory should have no violations reported"

    # Verify that non-excluded violations ARE still present (not over-broad exclusion)
    non_excluded_violations = [v["file"] for v in violations if "excluded" not in v["file"]]
    assert len(non_excluded_violations) > 0, "Non-excluded file's violations should be present"


def test_reports_tool_identity():
    runner = PhpmdComplexityRunner()

    assert runner.tool_name == "phpmd-codesize"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"php"})


@pytest.mark.slow
def test_tags_codesize_and_unusedcode_violations_separately(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            "src/A.php": _COMPLEX_METHOD,
            "src/B.php": _UNUSED_VARIABLE_METHOD,
        },
    )

    runner = PhpmdComplexityRunner()
    result = runner.run(repo_path, exclude_paths=[])

    violations = result.raw_output["violations"]
    codesize = [v for v in violations if v["ruleset"] == "codesize"]
    unusedcode = [v for v in violations if v["ruleset"] == "unusedcode"]
    assert codesize and all("complexity" in v for v in codesize)
    assert unusedcode and all(v.get("rule") == "UnusedLocalVariable" for v in unusedcode)
    assert all(v.get("class") == "A" for v in codesize)
    assert any(v.get("method") == "classify" for v in codesize)
    # UnusedLocalVariable, unlike UnusedPrivateMethod, carries no class/method
    # attribute at all (confirmed empirically against real phpmd output) -- the
    # key only expects the attribute to be present when phpmd provides it.
    assert all(v.get("class") is None for v in unusedcode)


_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "runners" / "phpmd"


def _pmd(body: str) -> str:
    return f'<?xml version="1.0" encoding="UTF-8" ?>\n<pmd version="3.0.0">{body}</pmd>\n'


def test_parses_real_phpmd_xml_into_tagged_relative_violations(tmp_path, fake_tool):
    stdout = (
        (_FIXTURE_DIR / "codesize-and-unusedcode.xml")
        .read_text()
        .replace("{target}", str(tmp_path))
    )
    calls = fake_tool(phpmd_complexity_runner, stdout=stdout, returncode=2)

    result = PhpmdComplexityRunner().run(tmp_path, exclude_paths=[])

    assert [c[:2] for c in calls[:2]] == [
        ["composer", "init"],
        ["composer", "require"],
    ]
    assert result.exit_code == 2
    assert result.command == " ".join(calls[2])
    assert calls[2][1:] == [str(tmp_path), "xml", "codesize,unusedcode", "--exclude=vendor/*"]
    # The NPathComplexity violation has no "Cyclomatic Complexity of N" text: dropped.
    assert result.raw_output["violations"] == [
        {
            "ruleset": "codesize",
            "file": "src/A.php",
            "line": 5,
            "complexity": 16,
            "class": "A",
            "method": "classify",
        },
        {
            "ruleset": "unusedcode",
            "file": "src/B.php",
            "line": 7,
            "rule": "UnusedLocalVariable",
            "message": "Avoid unused local variables such as '$unused'.",
            "class": None,
            "method": None,
        },
    ]


def test_keeps_stdout_and_no_violations_when_phpmd_output_is_not_xml(tmp_path, fake_tool):
    fake_tool(phpmd_complexity_runner, stdout="PHP Fatal error: boom", returncode=1)

    result = PhpmdComplexityRunner().run(tmp_path, exclude_paths=[])

    assert result.exit_code == 1
    assert result.raw_output == {"violations": [], "stdout": "PHP Fatal error: boom"}


def test_passes_one_exclude_flag_per_path_and_skips_paths_outside_the_target(tmp_path, fake_tool):
    excluded_dir = tmp_path / "src" / "excluded"
    excluded_dir.mkdir(parents=True)
    excluded_file = tmp_path / "src" / "Legacy.php"
    excluded_file.write_text("<?php\n")
    outside = tmp_path.parent / "elsewhere"
    calls = fake_tool(phpmd_complexity_runner, stdout=_pmd(""))

    PhpmdComplexityRunner().run(tmp_path, exclude_paths=[excluded_dir, excluded_file, outside])

    assert calls[2][4:] == [
        "--exclude=vendor/*",
        "--exclude=src/excluded/*",
        "--exclude=src/Legacy.php",
    ]


def test_ignores_unknown_rulesets_and_defaults_missing_attributes(tmp_path, fake_tool):
    body = (
        '<file name="x.php">'
        '<violation ruleset="Naming Rules" rule="ShortVariable">short</violation>'
        '<violation ruleset="Unused Code Rules" rule="UnusedPrivateMethod" class="K" method="m">'
        "  Avoid unused private methods.  </violation>"
        '<violation ruleset="Unused Code Rules" rule="UnusedFormalParameter"/>'
        '<violation ruleset="Code Size Rules"/>'
        "</file>"
    )
    fake_tool(phpmd_complexity_runner, stdout=_pmd(body))

    result = PhpmdComplexityRunner().run(tmp_path, exclude_paths=[])

    assert result.raw_output["violations"] == [
        {
            "ruleset": "unusedcode",
            "file": "x.php",
            "line": 0,
            "rule": "UnusedPrivateMethod",
            "message": "Avoid unused private methods.",
            "class": "K",
            "method": "m",
        },
        {
            "ruleset": "unusedcode",
            "file": "x.php",
            "line": 0,
            "rule": "UnusedFormalParameter",
            "message": "",
            "class": None,
            "method": None,
        },
    ]
