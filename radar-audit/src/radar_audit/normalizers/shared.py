from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Callable, Iterator
from pathlib import Path

from radar_core.enums import Confidence, FindingSeverity, FindingStatus, HumanVerdict, ScoreLevel
from radar_core.models.audit import Audit, ToolResult
from radar_core.models.finding import Finding, Recommendation
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun
from sqlmodel import Session, select


def get_or_create_scoring_run(
    session: Session, audit: Audit, methodology_version: MethodologyVersion
) -> ScoringRun:
    """Get or create the ScoringRun for this Audit + MethodologyVersion pair.

    Mirrors orchestrator.get_or_create_audit's reuse pattern, keyed on the model's
    (audit_id, methodology_version_id) unique constraint.
    """
    existing = session.exec(
        select(ScoringRun).where(
            ScoringRun.audit_id == audit.id,
            ScoringRun.methodology_version_id == methodology_version.id,
        )
    ).first()
    if existing is not None:
        return existing

    scoring_run = ScoringRun(audit_id=audit.id, methodology_version_id=methodology_version.id)
    session.add(scoring_run)
    session.commit()
    session.refresh(scoring_run)
    return scoring_run


class CriterionNotFoundError(ValueError):
    """Raised when a (category_name, criterion_name) pair isn't found in the seeded taxonomy."""


def get_criterion(
    session: Session,
    methodology_version_id: int,
    category_name: str,
    criterion_name: str,
) -> Criterion:
    """Look up a seeded Criterion by its category and criterion name, exactly as seeded from
    quality_framework_v1_0.yaml.
    """
    criterion = session.exec(
        select(Criterion)
        .join(Category, Category.id == Criterion.category_id)  # type: ignore[arg-type]
        .where(
            Category.methodology_version_id == methodology_version_id,
            Category.name == category_name,
            Criterion.name == criterion_name,
        )
    ).first()
    if criterion is None:
        raise CriterionNotFoundError(
            f"No criterion {criterion_name!r} in category {category_name!r} "
            f"for methodology_version_id={methodology_version_id}"
        )
    return criterion


# exit_code the orchestrator assigns to its crash-isolation record (see
# orchestrator._run_tool_safely).
CRASHED_EXIT_CODE = -1

# Shared between criteria 1.2 and 8.2, which both read the same design-doc-presence
# evidence. Provisional threshold, not yet calibrated against the real portfolio.
DESIGN_DOC_NON_TRIVIAL_LINE_THRESHOLD = 30


def add_finding_with_recommendation(
    session: Session, finding: Finding, recommendation_text: str
) -> Finding:
    """Add a Finding and its Recommendation together, in the same transaction.

    A Recommendation FKs to the Finding it belongs to, so the Finding must be
    flushed first to get its id assigned without ending the transaction (the
    caller is still free to commit whenever it commits the rest of its work).
    """
    session.add(finding)
    session.flush()
    session.add(Recommendation(finding_id=finding.id, text=recommendation_text))
    return finding


def get_repository_path(session: Session, scoring_run: ScoringRun) -> Path:
    """Resolve the on-disk path of the repository being scored.

    For normalizers that read the audited repo's own files directly (no
    ToolRunner/ToolResult involved), unlike every other normalizer in this module.

    Note: normalizers using this helper read the repository's current on-disk state
    at score time, which may differ from the commit the audit ran against if the
    repository has moved to a different commit or been locally modified since.
    """
    audit = session.get(Audit, scoring_run.audit_id)
    assert audit is not None
    repository = session.get(Repository, audit.repository_id)
    assert repository is not None
    return Path(repository.path)


def score_design_doc_evidence(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_results: list[ToolResult],
    *,
    missing_description: str,
    missing_recommendation: str,
    trivial_description: Callable[[str, int], str],
    trivial_recommendation: Callable[[str], str],
) -> Score | None:
    """Score a criterion from the design-doc-presence evidence (DESIGN.md/ARCHITECTURE.md/ADR).

    Shared by criteria 1.2 and 8.2, which read the same evidence under two different
    framings (architecture fidelity vs. documentation completeness) -- cross-referenced
    per the Quality Framework, not double-weighted. Callers supply their own Finding/
    Recommendation text; the evidence filter and the 0/6/10 banding are identical.
    """
    relevant = [
        r for r in tool_results if r.tool_name == "design-doc-presence" and r.exit_code == 0
    ]
    if not relevant:
        return None

    tool_result = relevant[0]
    found_path = tool_result.raw_output.get("found_path")
    non_blank_lines = tool_result.raw_output.get("non_blank_lines", 0)

    if found_path is None:
        value = 0.0
        _add_design_doc_finding(
            session,
            scoring_run,
            criterion,
            tool_result,
            missing_description,
            missing_recommendation,
        )
    elif non_blank_lines >= DESIGN_DOC_NON_TRIVIAL_LINE_THRESHOLD:
        value = 10.0
    else:
        value = 6.0
        _add_design_doc_finding(
            session,
            scoring_run,
            criterion,
            tool_result,
            trivial_description(found_path, non_blank_lines),
            trivial_recommendation(found_path),
        )

    score = Score(
        scoring_run_id=scoring_run.id,
        criterion_id=criterion.id,
        level=ScoreLevel.CRITERION,
        value=value,
        confidence=Confidence.MEDIUM,
    )
    session.add(score)
    session.commit()
    session.refresh(score)
    return score


def _add_design_doc_finding(
    session: Session,
    scoring_run: ScoringRun,
    criterion: Criterion,
    tool_result: ToolResult,
    description: str,
    recommendation_text: str,
) -> None:
    add_finding_with_recommendation(
        session,
        Finding(
            scoring_run_id=scoring_run.id,
            criterion_id=criterion.id,
            tool_result_id=tool_result.id,
            severity=FindingSeverity.LOW,
            description=description,
            confidence=Confidence.MEDIUM,
            status=FindingStatus.OPEN,
            human_verdict=HumanVerdict.UNREVIEWED,
        ),
        recommendation_text,
    )


def has_success_payload(tool_result: ToolResult, payload_key: str) -> bool:
    """Tell whether a ToolResult carries a real, successfully parsed payload.

    Security runners whose exit code is non-zero on findings (pip-audit, pnpm,
    composer) cannot be filtered on exit code alone, so success is signalled by the
    presence of the parsed payload list under `payload_key`. A failed run (orchestrator
    crash record, unparsable tool output, tool-reported error) omits that key or sets
    an `error` key, and must be treated as missing data rather than as a clean result.
    """
    if tool_result.exit_code == CRASHED_EXIT_CODE:
        return False
    raw_output = tool_result.raw_output
    if not isinstance(raw_output, dict) or "error" in raw_output:
        return False
    return isinstance(raw_output.get(payload_key), list)


_PROD_COMPOSE_CANDIDATES = (
    "docker-compose.prod.yml",
    "docker-compose.production.yml",
    "compose.prod.yml",
    "compose.prod.yaml",
)


def find_prod_compose(target_path: Path) -> Path | None:
    """Find the repository's production Docker Compose file, if any.

    Shared by criteria 7.2 (D11) and 9.3, which both use its presence as the
    signal for "this repo deploys a long-lived service" -- 9.3's health-check
    criterion is N/A using the same reasoning D11 already established for 7.2.
    """
    for candidate in _PROD_COMPOSE_CANDIDATES:
        candidate_path = target_path / candidate
        if candidate_path.is_file():
            return candidate_path
    return None


_PACKAGE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+")


def _package_name(spec: str) -> str:
    match = _PACKAGE_NAME_PATTERN.match(spec.strip())
    return match.group(0).lower() if match else ""


def _pyproject_dependency_names(data: dict[str, object]) -> set[str]:
    names: set[str] = set()

    project = data.get("project")
    if isinstance(project, dict):
        dependencies = project.get("dependencies")
        if isinstance(dependencies, list):
            names.update(_package_name(dep) for dep in dependencies if isinstance(dep, str))
        optional = project.get("optional-dependencies")
        if isinstance(optional, dict):
            for group in optional.values():
                if isinstance(group, list):
                    names.update(_package_name(dep) for dep in group if isinstance(dep, str))

    tool = data.get("tool")
    if isinstance(tool, dict):
        poetry = tool.get("poetry")
        if isinstance(poetry, dict):
            dependencies = poetry.get("dependencies")
            if isinstance(dependencies, dict):
                names.update(key.lower() for key in dependencies)

    return names


def python_dependency_names(candidate_dirs: list[Path]) -> set[str]:
    """Collect dependency names declared in pyproject.toml/requirements.txt.

    Searches every candidate directory (typically the repo root plus one level
    of subprojects from discover_subprojects) since a monorepo keeps its
    manifest below the root, not at it.
    """
    names: set[str] = set()
    for directory in candidate_dirs:
        pyproject_path = directory / "pyproject.toml"
        if pyproject_path.is_file():
            try:
                data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
                data = None
            if isinstance(data, dict):
                names.update(_pyproject_dependency_names(data))

        requirements_path = directory / "requirements.txt"
        if requirements_path.is_file():
            try:
                lines = requirements_path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                lines = []
            names.update(
                _package_name(line)
                for line in lines
                if line.strip() and not line.strip().startswith("#")
            )
    return names


def npm_dependency_names(candidate_dirs: list[Path]) -> set[str]:
    """Collect dependency names declared in package.json's dependencies/devDependencies."""
    names: set[str] = set()
    for directory in candidate_dirs:
        manifest_path = directory / "package.json"
        if not manifest_path.is_file():
            continue
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        for key in ("dependencies", "devDependencies"):
            section = data.get(key)
            if isinstance(section, dict):
                names.update(k.lower() for k in section)
    return names


def composer_dependency_names(candidate_dirs: list[Path]) -> set[str]:
    """Collect dependency names declared in composer.json's require/require-dev."""
    names: set[str] = set()
    for directory in candidate_dirs:
        manifest_path = directory / "composer.json"
        if not manifest_path.is_file():
            continue
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        for key in ("require", "require-dev"):
            section = data.get(key)
            if isinstance(section, dict):
                names.update(k.lower() for k in section)
    return names


_SOURCE_EXTENSIONS = frozenset({".py", ".js", ".ts", ".jsx", ".tsx", ".php"})
# Matches the _SKIP_DIRNAMES set already used by ruff_runner.py/mypy_runner.py/
# static_loc_runner.py/hadolint_runner.py/integration_test_runner.py for the same
# target_path -- .venv and __pycache__ are mandatory here too, not just node_modules/
# vendor, since target_path is a developer's live checkout, not a fresh clone.
_EXCLUDED_SOURCE_DIRNAMES = frozenset(
    {"node_modules", "vendor", ".git", "dist", "build", ".venv", "__pycache__"}
)


def iter_source_files(target_path: Path) -> Iterator[Path]:
    """Walk the repo's own source files, pruning vendored/build directories during
    the walk itself (not filtering results after rglob), so node_modules/.venv/vendor
    are never recursed into at all.

    Shared by criteria 9.2 and 9.3, which both grep source text for a simple
    marker (a DSN assignment, a health-check route path) rather than parsing
    per-framework routing syntax.
    """
    for dirpath, dirnames, filenames in target_path.walk(top_down=True):
        dirnames[:] = [name for name in dirnames if name not in _EXCLUDED_SOURCE_DIRNAMES]
        for filename in filenames:
            if Path(filename).suffix in _SOURCE_EXTENSIONS:
                yield dirpath / filename
