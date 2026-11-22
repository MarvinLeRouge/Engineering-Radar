"""Builds the v1 publication payload from one local scoring run (ADR 0014).

Kept apart from `radar_core.publication` on purpose: this module reads the local audit
tables, and radar-online imports the contract module but must never load them.
Only the fields the contract defines are read; criteria, findings, recommendations,
paths and notes are never queried, so they cannot leak.
"""

from __future__ import annotations

import re

from sqlmodel import Session, col, select

from radar_core.db import persisted_id
from radar_core.enums import ScoreLevel
from radar_core.models.audit import Audit
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun
from radar_core.publication import (
    PublicationPayload,
    PublishedCategory,
    PublishedRepositoryRef,
)

_NOT_SLUG_CHARS = re.compile(r"[^a-z0-9]+")


def repository_slug(name: str) -> str:
    """Return the public slug of a local repository name: lowercase, runs of other
    characters turned into one hyphen, no leading or trailing hyphen."""
    return _NOT_SLUG_CHARS.sub("-", name.lower()).strip("-")


def build_publication_payload(session: Session, scoring_run: ScoringRun) -> PublicationPayload:
    """Return the sanitized payload of `scoring_run`: global and category scores only.

    Raises:
        pydantic.ValidationError: a local value does not fit the contract (for
            example a repository name with no letter or digit), so nothing is sent.
    """
    audit = session.get(Audit, scoring_run.audit_id)
    version = session.get(MethodologyVersion, scoring_run.methodology_version_id)
    assert audit is not None and version is not None
    repository = session.get(Repository, audit.repository_id)
    assert repository is not None
    return PublicationPayload(
        schema_version=1,
        repository=PublishedRepositoryRef(
            slug=repository_slug(repository.name), display_name=repository.name
        ),
        commit_sha=audit.commit_sha,
        scored_at=scoring_run.scored_at,
        methodology_version=version.version_label,
        global_score=scoring_run.global_score,
        categories=_categories(session, scoring_run),
    )


def _categories(session: Session, scoring_run: ScoringRun) -> list[PublishedCategory]:
    categories = session.exec(
        select(Category)
        .where(Category.methodology_version_id == scoring_run.methodology_version_id)
        .order_by(col(Category.order))
    ).all()
    scores = {
        score.category_id: score
        for score in session.exec(
            select(Score).where(
                Score.scoring_run_id == persisted_id(scoring_run),
                Score.level == ScoreLevel.CATEGORY,
            )
        )
    }
    implemented = set(
        session.exec(
            select(Criterion.category_id).where(
                col(Criterion.category_id).in_([c.id for c in categories]),
                Criterion.implemented,
            )
        )
    )
    published = []
    for category in categories:
        score = scores.get(category.id)
        is_implemented = category.id in implemented
        # The contract only lets a scored, implemented category carry a value.
        valued = score if is_implemented else None
        published.append(
            PublishedCategory(
                name=category.name,
                order=category.order,
                weight=category.weight,
                status="scored" if score is not None else "not_yet_audited",
                implemented=is_implemented,
                value=valued.value if valued else None,
                confidence=valued.confidence if valued else None,
            )
        )
    return published
