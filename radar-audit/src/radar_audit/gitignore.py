from __future__ import annotations

from pathlib import Path

import pathspec

GitignoreSpec = pathspec.PathSpec[pathspec.pattern.Pattern]


def load_gitignore_spec(repo_root: Path) -> GitignoreSpec:
    """Load the audited repo's own top-level .gitignore as a matchable spec.

    Only the repo-root .gitignore is consulted, not nested .gitignore files
    or .git/info/exclude -- good enough to keep an audited repo's own
    scratch/local content (e.g. a gitignored docs/work-in-progress/ folder)
    out of static-analysis criteria, without reimplementing git's full
    ignore-resolution rules. Returns an empty (matches-nothing) spec when
    there is no .gitignore file.
    """
    gitignore_path = repo_root / ".gitignore"
    if not gitignore_path.is_file():
        return pathspec.PathSpec.from_lines("gitignore", [])
    patterns = gitignore_path.read_text(errors="ignore").splitlines()
    return pathspec.PathSpec.from_lines("gitignore", patterns)


def is_git_ignored(file_path: Path, repo_root: Path, spec: GitignoreSpec) -> bool:
    """Tell whether file_path (absolute, under repo_root) matches the given spec."""
    relative = file_path.relative_to(repo_root)
    return spec.match_file(str(relative))
