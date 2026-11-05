import subprocess

from radar_audit.worktree import compute_exclude_paths, compute_ignored_paths

from tests.git_helpers import init_git_repo


def test_repo_with_no_extra_worktrees_returns_empty_list(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)

    assert compute_exclude_paths(repo_path) == []


def test_repo_with_a_worktree_excludes_it(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    worktree_path = tmp_path / "repo-worktree"
    subprocess.run(
        ["git", "-C", str(repo_path), "worktree", "add", "-b", "wt-branch", str(worktree_path)],
        check=True,
        capture_output=True,
    )

    result = compute_exclude_paths(repo_path)

    assert result == [worktree_path.resolve()]


def test_main_repo_path_itself_is_never_in_the_exclude_list(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)
    worktree_path = tmp_path / "repo-worktree"
    subprocess.run(
        ["git", "-C", str(repo_path), "worktree", "add", "-b", "wt-branch", str(worktree_path)],
        check=True,
        capture_output=True,
    )

    result = compute_exclude_paths(repo_path)

    assert repo_path.resolve() not in result


def test_ignored_paths_list_ignored_dirs_whole_and_ignored_files(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(
        repo_path,
        files={
            ".gitignore": "/storage/phpstan\nnode_modules/\n*.log\n",
            "app/A.php": "<?php\n",
            # Tracked siblings: a directory holding only ignored content is listed whole.
            "storage/app/.gitkeep": "",
            "web/package.json": "{}\n",
        },
    )
    (repo_path / "storage" / "phpstan" / "cache").mkdir(parents=True)
    (repo_path / "storage" / "phpstan" / "cache" / "Container.php").write_text("<?php\n")
    (repo_path / "web" / "node_modules" / "flatted").mkdir(parents=True)
    (repo_path / "debug.log").write_text("x\n")

    result = compute_ignored_paths(repo_path)

    assert sorted(result) == sorted(
        [
            repo_path / "storage" / "phpstan",
            repo_path / "web" / "node_modules",
            repo_path / "debug.log",
        ]
    )


def test_ignored_paths_is_empty_when_nothing_is_ignored(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path)

    assert compute_ignored_paths(repo_path) == []
