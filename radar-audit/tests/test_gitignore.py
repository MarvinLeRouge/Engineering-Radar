from radar_audit.gitignore import is_git_ignored, load_gitignore_spec

from tests.git_helpers import init_git_repo


def test_matches_a_simple_ignored_path(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={".gitignore": "docs/work-in-progress/\n"})
    spec = load_gitignore_spec(repo_path)

    ignored = repo_path / "docs" / "work-in-progress" / "scratch.ts"
    kept = repo_path / "docs" / "readme.md"

    assert is_git_ignored(ignored, repo_path, spec) is True
    assert is_git_ignored(kept, repo_path, spec) is False


def test_returns_an_empty_spec_when_there_is_no_gitignore(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={"src/a.py": "x = 1\n"})
    spec = load_gitignore_spec(repo_path)

    assert is_git_ignored(repo_path / "src" / "a.py", repo_path, spec) is False


def test_matches_wildcard_patterns(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={".gitignore": "*.log\nbuild/\n"})
    spec = load_gitignore_spec(repo_path)

    assert is_git_ignored(repo_path / "debug.log", repo_path, spec) is True
    assert is_git_ignored(repo_path / "src" / "nested.log", repo_path, spec) is True
    assert is_git_ignored(repo_path / "build" / "out.js", repo_path, spec) is True
    assert is_git_ignored(repo_path / "src" / "a.js", repo_path, spec) is False


def test_blank_and_comment_lines_in_gitignore_are_not_treated_as_patterns(tmp_path):
    repo_path = tmp_path / "repo"
    init_git_repo(repo_path, files={".gitignore": "# a comment\n\nscratch/\n"})
    spec = load_gitignore_spec(repo_path)

    assert is_git_ignored(repo_path / "scratch" / "x.py", repo_path, spec) is True
    assert is_git_ignored(repo_path / "a comment", repo_path, spec) is False
