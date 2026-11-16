import json
import subprocess
from pathlib import Path

import pytest
from radar_audit.runners import phpstan_runner
from radar_audit.runners.phpstan_runner import PhpstanRunner

from tests.git_helpers import init_git_repo


def _init_composer_project(repo_path):
    (repo_path / "composer.json").write_text('{"name": "fixture/fixture"}\n')
    subprocess.run(
        ["composer", "install", "--no-interaction"],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )


@pytest.mark.slow
def test_reports_no_errors_on_well_typed_php(tmp_path):
    repo_path = tmp_path / "repo"
    php_source = (
        "<?php\n\nclass A\n{\n"
        "    public function add(int $a, int $b): int\n"
        "    {\n        return $a + $b;\n    }\n}\n"
    )
    init_git_repo(repo_path, files={"src/A.php": php_source})
    _init_composer_project(repo_path)

    runner = PhpstanRunner()
    result = runner.run(repo_path, exclude_paths=[])

    assert result.exit_code == 0
    assert result.raw_output["totals"]["errors"] == 0


@pytest.mark.slow
def test_reverts_composer_json_and_lock_byte_identical(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/A.php": "<?php\n\nclass A\n{\n}\n"})
    _init_composer_project(repo_path)
    original_json = (repo_path / "composer.json").read_bytes()
    original_lock = (repo_path / "composer.lock").read_bytes()

    runner = PhpstanRunner()
    runner.run(repo_path, exclude_paths=[])

    assert (repo_path / "composer.json").read_bytes() == original_json
    assert (repo_path / "composer.lock").read_bytes() == original_lock


def test_reports_tool_identity():
    runner = PhpstanRunner()

    assert runner.tool_name == "phpstan"
    assert runner.scope == "subproject"
    assert runner.supported_stacks == frozenset({"php"})


def test_build_neon_content_always_excludes_target_vendor(tmp_path):
    runner = PhpstanRunner()

    neon = runner._build_neon_content(is_laravel=False, target_path=tmp_path, exclude_paths=[])

    assert f"{tmp_path}/vendor/*" in neon


def test_build_neon_content_includes_caller_exclude_paths(tmp_path):
    runner = PhpstanRunner()
    excluded_dir = tmp_path / "some" / "excluded" / "dir"

    neon = runner._build_neon_content(
        is_laravel=False, target_path=tmp_path, exclude_paths=[excluded_dir]
    )

    assert f"{excluded_dir}/*" in neon
    assert f"{tmp_path}/vendor/*" in neon


def test_build_neon_content_includes_block_only_when_laravel(tmp_path):
    runner = PhpstanRunner()

    laravel_neon = runner._build_neon_content(
        is_laravel=True, target_path=tmp_path, exclude_paths=[]
    )
    bare_neon = runner._build_neon_content(is_laravel=False, target_path=tmp_path, exclude_paths=[])

    assert "includes:" in laravel_neon
    assert "vendor/larastan/larastan/extension.neon" in laravel_neon
    assert "includes:" not in bare_neon


def test_build_neon_content_excludes_a_single_file_as_is(tmp_path):
    runner = PhpstanRunner()
    test_file = tmp_path / "src" / "UserTest.php"
    test_file.parent.mkdir()
    test_file.write_text("<?php\n")

    neon = runner._build_neon_content(
        is_laravel=False, target_path=tmp_path, exclude_paths=[test_file]
    )

    assert f"- '{test_file}'\n" in neon


def test_build_neon_content_quotes_entries_with_neon_special_characters(tmp_path):
    # Excluded paths now include every git-ignored file, whose names can hold # or :.
    odd_file = tmp_path / "it's #1: debug.log"
    odd_file.write_text("x\n")

    neon = PhpstanRunner()._build_neon_content(
        is_laravel=False, target_path=tmp_path, exclude_paths=[odd_file]
    )

    assert f"- '{tmp_path}/it''s #1: debug.log'\n" in neon


@pytest.mark.slow
def test_reports_file_paths_relative_to_the_target(tmp_path):
    repo_path = tmp_path / "repo"
    php_source = "<?php\n\nfunction broken(): int\n{\n    return 'not an int';\n}\n"
    init_git_repo(repo_path, files={"src/Broken.php": php_source})
    _init_composer_project(repo_path)

    result = PhpstanRunner().run(repo_path, exclude_paths=[])

    assert list(result.raw_output["files"]) == ["src/Broken.php"]


_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "runners" / "phpstan"


def _phpstan_call(command: list[str]) -> bool:
    return command[0] == "vendor/bin/phpstan"


def test_relativizes_file_keys_of_real_phpstan_json(tmp_path, fake_tool):
    stdout = (_FIXTURE_DIR / "file-error.json").read_text().replace("{target}", str(tmp_path))
    calls = fake_tool(phpstan_runner, stdout=stdout, returncode=1)

    result = PhpstanRunner().run(tmp_path, exclude_paths=[])

    assert [c[:2] for c in calls] == [
        ["composer", "require"],
        ["vendor/bin/phpstan", "analyse"],
        ["composer", "install"],
    ]
    assert calls[0] == ["composer", "require", "--dev", "phpstan/phpstan", "--no-interaction"]
    neon = str(tmp_path / "_radar_audit_phpstan.neon")
    assert calls[1] == [
        "vendor/bin/phpstan",
        "analyse",
        "--configuration",
        neon,
        "--error-format=json",
        "--no-progress",
        str(tmp_path),
    ]
    assert result.exit_code == 1
    assert result.command == " ".join(calls[1])
    assert list(result.raw_output["files"]) == ["src/Broken.php"]
    assert result.raw_output["files"]["src/Broken.php"]["messages"][0]["identifier"] == (
        "return.type"
    )


def test_writes_neon_during_analysis_and_removes_it_afterwards(tmp_path, fake_tool):
    seen = {}
    excluded = tmp_path / "tests"
    excluded.mkdir()

    def respond(command, cwd):
        if _phpstan_call(command):
            seen["neon"] = Path(command[3]).read_text()
            seen["cwd"] = cwd

    fake_tool(phpstan_runner, stdout="{}", respond=respond)

    PhpstanRunner().run(tmp_path, exclude_paths=[excluded])

    assert seen["cwd"] == tmp_path
    assert f"'{tmp_path}/vendor/*'" in seen["neon"]
    assert f"'{tmp_path}/tests/*'" in seen["neon"]
    assert not (tmp_path / "_radar_audit_phpstan.neon").exists()


def test_restores_composer_files_byte_identical_after_the_run(tmp_path, fake_tool):
    (tmp_path / "composer.json").write_bytes(b'{"name": "a/b"}\n')
    (tmp_path / "composer.lock").write_bytes(b'{"packages": []}\n')

    def respond(command, cwd):
        if command[:2] == ["composer", "require"]:
            (tmp_path / "composer.json").write_text("mutated by require")
            (tmp_path / "composer.lock").write_text("mutated by require")

    fake_tool(phpstan_runner, stdout="{}", respond=respond)

    PhpstanRunner().run(tmp_path, exclude_paths=[])

    assert (tmp_path / "composer.json").read_bytes() == b'{"name": "a/b"}\n'
    assert (tmp_path / "composer.lock").read_bytes() == b'{"packages": []}\n'


def test_removes_composer_files_the_run_created(tmp_path, fake_tool):
    def respond(command, cwd):
        if command[:2] == ["composer", "require"]:
            (tmp_path / "composer.json").write_text("{}")
            (tmp_path / "composer.lock").write_text("{}")

    fake_tool(phpstan_runner, stdout="{}", respond=respond)

    PhpstanRunner().run(tmp_path, exclude_paths=[])

    assert not (tmp_path / "composer.json").exists()
    assert not (tmp_path / "composer.lock").exists()


def test_cleans_up_and_reinstalls_when_phpstan_crashes(tmp_path, fake_tool):
    (tmp_path / "composer.json").write_bytes(b'{"name": "a/b"}\n')

    def respond(command, cwd):
        if command[:2] == ["composer", "require"]:
            (tmp_path / "composer.json").write_text("mutated")
        if _phpstan_call(command):
            raise subprocess.TimeoutExpired(command, 120)

    calls = fake_tool(phpstan_runner, respond=respond)

    with pytest.raises(subprocess.TimeoutExpired):
        PhpstanRunner().run(tmp_path, exclude_paths=[])

    assert (tmp_path / "composer.json").read_bytes() == b'{"name": "a/b"}\n'
    assert not (tmp_path / "_radar_audit_phpstan.neon").exists()
    assert calls[-1][:2] == ["composer", "install"]


def test_installs_larastan_and_includes_its_extension_for_a_laravel_target(tmp_path, fake_tool):
    (tmp_path / "composer.json").write_text(json.dumps({"require": {"laravel/framework": "^11"}}))
    seen = {}

    def respond(command, cwd):
        if _phpstan_call(command):
            seen["neon"] = Path(command[3]).read_text()

    calls = fake_tool(phpstan_runner, stdout="{}", respond=respond)

    PhpstanRunner().run(tmp_path, exclude_paths=[])

    assert calls[0][3:5] == ["phpstan/phpstan", "larastan/larastan"]
    assert seen["neon"].startswith("includes:\n    - vendor/larastan/larastan/extension.neon\n")


def test_does_not_treat_a_composer_json_without_laravel_as_laravel(tmp_path, fake_tool):
    (tmp_path / "composer.json").write_text(json.dumps({"name": "a/b"}))
    calls = fake_tool(phpstan_runner, stdout="{}")

    PhpstanRunner().run(tmp_path, exclude_paths=[])

    assert "larastan/larastan" not in calls[0]


def test_keeps_stdout_and_stderr_when_phpstan_output_is_not_json(tmp_path, fake_tool):
    fake_tool(phpstan_runner, stdout="Fatal error", stderr="trace", returncode=255)

    result = PhpstanRunner().run(tmp_path, exclude_paths=[])

    assert result.exit_code == 255
    assert result.raw_output == {"stdout": "Fatal error", "stderr": "trace"}


@pytest.mark.parametrize("stdout", ["[]", '{"files": []}', '{"totals": {"errors": 0}}'])
def test_leaves_json_without_a_files_mapping_untouched(tmp_path, fake_tool, stdout):
    fake_tool(phpstan_runner, stdout=stdout)

    result = PhpstanRunner().run(tmp_path, exclude_paths=[])

    assert result.raw_output == json.loads(stdout)
