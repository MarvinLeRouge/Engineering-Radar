"""Audit scope: the out-of-scope zones (tests, migrations) some criteria ignore.

Each runner lists the zones its criterion does not judge in an optional
`excluded_zones` attribute; the orchestrator adds the matching paths to that
runner's `exclude_paths`, so the tool itself never analyzes them and its
ratios (clean files / analyzed files) stay correct. Rationale and the per-criterion
table: docs/quality-framework.md, "Audit scope".
"""

from __future__ import annotations

import fnmatch
import os
from pathlib import Path

TESTS = "tests"
MIGRATIONS = "migrations"
TESTS_AND_MIGRATIONS = frozenset({TESTS, MIGRATIONS})

# Directory names seen across the portfolio: "tests" (Python, Laravel), "test" (NestJS),
# "__tests__" (Vue/Vitest), "e2e" (Playwright).
_TEST_DIRNAMES = frozenset({"tests", "test", "__tests__", "e2e"})
_TEST_FILE_PATTERNS = ("test_*.py", "*_test.py", "conftest.py", "*.spec.*", "*.test.*")
# A "*.spec.*" data file (openapi.spec.yaml) is not a test: only code files qualify.
_CODE_SUFFIXES = frozenset(
    {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts", ".vue", ".php"}
)
# Never walked (besides every dot-directory): dependencies, build and coverage output.
_SKIP_DIRNAMES = frozenset(
    {"node_modules", "vendor", "venv", "dist", "build", "__pycache__", "coverage", "htmlcov"}
)


def is_test_path(relative_file: str) -> bool:
    """Whether a file path reported by a tool belongs to the tests zone."""
    path = Path(relative_file)
    return any(part in _TEST_DIRNAMES for part in path.parent.parts) or _is_test_file(path.name)


def _is_test_file(filename: str) -> bool:
    return Path(filename).suffix in _CODE_SUFFIXES and any(
        fnmatch.fnmatch(filename, pattern) for pattern in _TEST_FILE_PATTERNS
    )


def _is_migrations_dir(directory: Path) -> bool:
    # "alembic" alone could be an unrelated package: require Alembic's own layout.
    if directory.name == "alembic":
        return (directory / "versions").is_dir()
    return directory.name == "migrations"


def out_of_scope_paths(target_path: Path, zones: frozenset[str]) -> list[Path]:
    """Return the directories and files under `target_path` that belong to `zones`.

    A matching directory is returned whole and not walked further; a test file
    is returned on its own only when it sits outside a test directory (e.g. a
    NestJS `*.spec.ts` next to its source file). Paths keep the form of `target_path`
    (not resolved), since runners call `excluded.relative_to(target_path)`.
    """
    if not zones:
        return []
    found: list[Path] = []
    for root, dirnames, filenames in os.walk(target_path):
        root_path = Path(root)
        kept = []
        for dirname in sorted(dirnames):
            directory = root_path / dirname
            if dirname in _SKIP_DIRNAMES or dirname.startswith("."):
                continue
            if (TESTS in zones and dirname in _TEST_DIRNAMES) or (
                MIGRATIONS in zones and _is_migrations_dir(directory)
            ):
                found.append(directory)
                continue
            kept.append(dirname)
        dirnames[:] = kept
        if TESTS in zones:
            found.extend(
                root_path / filename for filename in sorted(filenames) if _is_test_file(filename)
            )
    return found


def exclusion_glob(excluded: Path, rendered: Path | str, directory_suffix: str) -> str:
    """Glob for one excluded path, written as `rendered` (absolute or relative).

    A directory gets `directory_suffix` (e.g. "/*"); a single excluded file is matched as is.
    """
    return str(rendered) if excluded.is_file() else f"{rendered}{directory_suffix}"
