"""Git discovery of what audits must skip: linked worktrees and git-ignored paths."""

from __future__ import annotations

import subprocess
from pathlib import Path


def compute_exclude_paths(repo_path: Path) -> list[Path]:
    """Return every worktree path linked to `repo_path`'s repo, excluding `repo_path` itself."""
    result = subprocess.run(
        ["git", "-C", str(repo_path), "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        check=True,
    )

    all_paths = [
        Path(line.removeprefix("worktree ")).resolve()
        for line in result.stdout.splitlines()
        if line.startswith("worktree ")
    ]

    main_path = repo_path.resolve()
    return [path for path in all_paths if path != main_path]


def compute_ignored_paths(repo_path: Path) -> list[Path]:
    """Return every git-ignored file under `repo_path`, and every fully ignored directory whole.

    Generated or third-party files (a tool cache such as Laravel's `storage/phpstan`,
    `node_modules`, build output) are not the repository's code, so no runner audits them.
    """
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_path),
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            "--directory",
            "-z",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return [repo_path / entry.rstrip("/") for entry in result.stdout.split("\0") if entry]
