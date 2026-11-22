"""Public read endpoints: profile, latest report, history and badge of published repositories.

Only ACTIVE accounts are visible, and nothing beyond the published payload and the
public names leaves the database (never the email). Every answer is cacheable for
five minutes, so a badge in a busy README does not hit SQLite on each view.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from radar_core.badge import BADGE_LABEL, BadgeResponse, badge_color
from radar_core.db import persisted_id
from sqlmodel import Session, col, select

from radar_online.dependencies import get_db_session
from radar_online.models import PublishedReport, PublishedRepository, User, UserStatus

_CACHE_CONTROL = "public, max-age=300"

router = APIRouter(prefix="/users", tags=["public"])


class PublicName(BaseModel):
    """A public slug and its display name, for a user or a repository."""

    slug: str
    display_name: str


class RepositorySummary(PublicName):
    """A published repository and the global score of its latest commit."""

    latest_global_score: float | None
    latest_scored_at: datetime | None


class Profile(PublicName):
    """A user's public profile and the repositories they publish."""

    repositories: list[RepositorySummary]


class PublicReport(BaseModel):
    """The latest published report of a repository: the stored v1 payload."""

    user: PublicName
    repository: PublicName
    uploaded_at: datetime
    report: dict[str, Any]


class HistoryCategory(BaseModel):
    """One category score at one commit."""

    name: str
    order: int
    value: float | None
    implemented: bool


class HistoryPoint(BaseModel):
    """The global and category scores of one published commit."""

    commit_sha: str
    scored_at: datetime
    global_score: float | None
    categories: list[HistoryCategory]


SessionDep = Annotated[Session, Depends(get_db_session)]


@router.get("/{user_slug}", response_model=Profile)
def get_profile(user_slug: str, response: Response, session: SessionDep) -> Profile:
    """Return the profile of an active user and the latest score of each of their repositories."""
    user = _active_user(session, user_slug)
    repositories = session.exec(
        select(PublishedRepository)
        .where(PublishedRepository.user_id == persisted_id(user))
        .order_by(col(PublishedRepository.slug))
    ).all()
    summaries = []
    for repository in repositories:
        latest = _latest_report(session, repository)
        summaries.append(
            RepositorySummary(
                slug=repository.slug,
                display_name=repository.display_name,
                latest_global_score=latest.global_score if latest else None,
                latest_scored_at=latest.scored_at if latest else None,
            )
        )
    response.headers["Cache-Control"] = _CACHE_CONTROL
    return Profile(slug=user.slug, display_name=user.display_name, repositories=summaries)


@router.get(
    "/{user_slug}/repositories/{repository_slug}/report",
    response_model=PublicReport,
    responses={404: {"description": "Unknown user or repository, or nothing published"}},
)
def get_report(
    user_slug: str, repository_slug: str, response: Response, session: SessionDep
) -> PublicReport:
    """Return the report of the most recently scored commit, whatever the upload order."""
    user = _active_user(session, user_slug)
    repository = _repository(session, user, repository_slug)
    report = _latest_report(session, repository)
    if report is None:
        raise HTTPException(status_code=404, detail="no published report")
    response.headers["Cache-Control"] = _CACHE_CONTROL
    return PublicReport(
        user=PublicName(slug=user.slug, display_name=user.display_name),
        repository=PublicName(slug=repository.slug, display_name=repository.display_name),
        uploaded_at=report.uploaded_at,
        report=report.payload,
    )


@router.get(
    "/{user_slug}/repositories/{repository_slug}/history",
    response_model=list[HistoryPoint],
    responses={404: {"description": "Unknown user or repository"}},
)
def get_history(
    user_slug: str, repository_slug: str, response: Response, session: SessionDep
) -> list[HistoryPoint]:
    """Return one point per published commit, oldest first.

    shortcut: unpaginated, fine for hundreds of commits; page it if a repository grows past that.
    """
    user = _active_user(session, user_slug)
    repository = _repository(session, user, repository_slug)
    reports = session.exec(
        select(PublishedReport)
        .where(PublishedReport.repository_id == persisted_id(repository))
        .order_by(col(PublishedReport.scored_at))
    ).all()
    response.headers["Cache-Control"] = _CACHE_CONTROL
    return [
        HistoryPoint(
            commit_sha=report.commit_sha,
            scored_at=report.scored_at,
            global_score=report.global_score,
            categories=[HistoryCategory(**c) for c in report.payload["categories"]],
        )
        for report in reports
    ]


@router.get("/{user_slug}/repositories/{repository_slug}/badge", response_model=BadgeResponse)
def get_badge(
    user_slug: str, repository_slug: str, response: Response, session: SessionDep
) -> BadgeResponse:
    """Return the shields.io badge of the latest global score, marked self-assessed.

    Always answers 200 so a badge image never breaks: grey "not published" when the
    user, the repository or a scored report is missing.
    """
    response.headers["Cache-Control"] = _CACHE_CONTROL
    report = None
    try:
        user = _active_user(session, user_slug)
        report = _latest_report(session, _repository(session, user, repository_slug))
    except HTTPException:
        pass
    if report is None or report.global_score is None:
        return BadgeResponse(label=BADGE_LABEL, message="not published", color="lightgrey")
    return BadgeResponse(
        label=BADGE_LABEL,
        message=f"{report.global_score:.1f}/10 (self-assessed)",
        color=badge_color(report.global_score),
    )


def _active_user(session: Session, slug: str) -> User:
    user = session.exec(
        select(User).where(User.slug == slug, User.status == UserStatus.ACTIVE)
    ).first()
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user


def _repository(session: Session, user: User, slug: str) -> PublishedRepository:
    repository = session.exec(
        select(PublishedRepository).where(
            PublishedRepository.user_id == persisted_id(user), PublishedRepository.slug == slug
        )
    ).first()
    if repository is None:
        raise HTTPException(status_code=404, detail="repository not found")
    return repository


def _latest_report(session: Session, repository: PublishedRepository) -> PublishedReport | None:
    return session.exec(
        select(PublishedReport)
        .where(PublishedReport.repository_id == persisted_id(repository))
        .order_by(col(PublishedReport.scored_at).desc())
    ).first()
