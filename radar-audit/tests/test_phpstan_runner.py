import subprocess

import pytest
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


def test_build_neon_content_excludes_what_git_ignores(tmp_path):
    # PHPStan's own cache (Laravel: storage/phpstan) holds generated PHP that it would analyse.
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={".gitignore": "/storage/phpstan\n/node_modules\n.env\n", "app/A.php": "<?php\n"},
    )
    (repo_path / "storage" / "phpstan" / "cache").mkdir(parents=True)
    (repo_path / "storage" / "phpstan" / "cache" / "Container.php").write_text("<?php\n")
    (repo_path / "node_modules" / "flatted" / "php").mkdir(parents=True)
    (repo_path / ".env").write_text("APP_KEY=\n")

    neon = PhpstanRunner()._build_neon_content(
        is_laravel=False, target_path=repo_path, exclude_paths=[]
    )

    assert f"- '{repo_path}/storage/phpstan/*'\n" in neon
    assert f"- '{repo_path}/node_modules/*'\n" in neon
    assert f"- '{repo_path}/.env'\n" in neon
    assert f"{repo_path}/app" not in neon


def test_build_neon_content_quotes_entries_with_neon_special_characters(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={".gitignore": "*.log\n"})
    (repo_path / "it's #1: debug.log").write_text("x\n")

    neon = PhpstanRunner()._build_neon_content(
        is_laravel=False, target_path=repo_path, exclude_paths=[]
    )

    assert f"- '{repo_path}/it''s #1: debug.log'\n" in neon


def test_build_neon_content_lists_ignored_paths_of_a_subproject_relative_to_it(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={".gitignore": "cache/\n", "backend/app/A.php": "<?php\n"})
    (repo_path / "backend" / "cache").mkdir()
    (repo_path / "backend" / "cache" / "C.php").write_text("<?php\n")

    neon = PhpstanRunner()._build_neon_content(
        is_laravel=False, target_path=repo_path / "backend", exclude_paths=[]
    )

    assert f"- '{repo_path}/backend/cache/*'\n" in neon


def test_build_neon_content_outside_a_git_repo_only_excludes_vendor(tmp_path):
    neon = PhpstanRunner()._build_neon_content(
        is_laravel=False, target_path=tmp_path, exclude_paths=[]
    )

    assert neon.count("        - ") == 1


@pytest.mark.slow
def test_reports_file_paths_relative_to_the_target(tmp_path):
    repo_path = tmp_path / "repo"
    php_source = "<?php\n\nfunction broken(): int\n{\n    return 'not an int';\n}\n"
    init_git_repo(repo_path, files={"src/Broken.php": php_source})
    _init_composer_project(repo_path)

    result = PhpstanRunner().run(repo_path, exclude_paths=[])

    assert list(result.raw_output["files"]) == ["src/Broken.php"]
