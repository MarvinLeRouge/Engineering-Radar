"""Report upload: `POST /api/reports`, authenticated by API key."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ValidationError
from radar_core.db import persisted_id
from radar_core.publication import PublicationPayload
from sqlmodel import Session, select

from radar_online.auth import require_user
from radar_online.dependencies import get_db_session
from radar_online.models import PublishedReport, PublishedRepository, User
from radar_online.rate_limit import SlidingWindowLimiter

# Design section 3: a v1 payload is a few KiB; anything larger is not a report.
MAX_BODY_BYTES = 64 * 1024

# A publish follows a local audit and scoring run: a handful per hour is the real ceiling.
UPLOADS_PER_HOUR = 20
upload_limiter = SlidingWindowLimiter(limit=UPLOADS_PER_HOUR, window_seconds=3600)

router = APIRouter(tags=["reports"])


class UploadResult(BaseModel):
    """Where the uploaded report is shown, relative to the radar-online host."""

    report_path: str


@router.post(
    "/reports",
    response_model=UploadResult,
    status_code=status.HTTP_201_CREATED,
    responses={
        200: {"description": "The report of this commit was replaced", "model": UploadResult},
        401: {"description": "Invalid or missing API key"},
        413: {"description": "Body larger than 64 KiB"},
        429: {"description": "More than 20 uploads in the last hour for this account"},
        422: {"description": "Payload does not match the v1 publication contract"},
    },
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": PublicationPayload.model_json_schema()}},
        }
    },
)
async def upload_report(
    request: Request,
    response: Response,
    user: Annotated[User, Depends(require_user)],
    session: Annotated[Session, Depends(get_db_session)],
) -> UploadResult:
    """Publish one commit's scores: create the repository on first upload, replace the
    report when this commit is already published. Only the validated payload is stored,
    never the raw body."""
    retry_after = upload_limiter.hit(str(persisted_id(user)))
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"upload limit reached: {UPLOADS_PER_HOUR} per hour",
            headers={"Retry-After": str(retry_after)},
        )
    payload = _parse(await request.body())
    repository = _get_or_create_repository(session, user, payload)
    report = session.exec(
        select(PublishedReport).where(
            PublishedReport.repository_id == persisted_id(repository),
            PublishedReport.commit_sha == payload.commit_sha,
        )
    ).first()
    if report is None:
        report = PublishedReport(repository_id=persisted_id(repository), **_report_fields(payload))
    else:
        response.status_code = status.HTTP_200_OK
        report.sqlmodel_update(_report_fields(payload))
    session.add(report)
    session.commit()
    return UploadResult(report_path=f"/u/{user.slug}/{repository.slug}")


def _parse(body: bytes) -> PublicationPayload:
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail="report larger than 64 KiB"
        )
    try:
        return PublicationPayload.model_validate_json(body)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.errors(include_url=False, include_context=False, include_input=False),
        ) from exc


def _get_or_create_repository(
    session: Session, user: User, payload: PublicationPayload
) -> PublishedRepository:
    repository = session.exec(
        select(PublishedRepository).where(
            PublishedRepository.user_id == persisted_id(user),
            PublishedRepository.slug == payload.repository.slug,
        )
    ).first()
    if repository is None:
        repository = PublishedRepository(
            user_id=persisted_id(user),
            slug=payload.repository.slug,
            display_name=payload.repository.display_name,
        )
    else:
        repository.display_name = payload.repository.display_name
    session.add(repository)
    session.flush()
    return repository


def _report_fields(payload: PublicationPayload) -> dict[str, Any]:
    return {
        "commit_sha": payload.commit_sha,
        "scored_at": payload.scored_at,
        "methodology_version": payload.methodology_version,
        "schema_version": payload.schema_version,
        "global_score": payload.global_score,
        "payload": payload.model_dump(mode="json"),
    }
