"""Sends one scoring run's sanitized payload to radar-online (FEAT-046).

Shared by radar-api (`POST /repositories/{id}/publish`) and `radar-audit publish`, so
both refuse the same runs and send the same bytes. The API key is only ever put in
the request header: no error message or log line carries it.
"""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlmodel import Session

from radar_core.models.audit import Audit
from radar_core.models.scoring import ScoringRun
from radar_core.publication_builder import build_publication_payload

_TIMEOUT_SECONDS = 15


class PublishError(RuntimeError):
    """Base class of every reason a scoring run was not published."""


class DirtyAuditError(PublishError):
    """The run scored a modified working tree, so its commit does not describe it."""


class PublishingNotConfiguredError(PublishError):
    """RADAR_ONLINE_URL or RADAR_ONLINE_API_KEY is missing, or the URL is not http(s)."""


class PublishFailedError(PublishError):
    """radar-online refused the report or could not be reached."""


def publish_scoring_run(session: Session, scoring_run: ScoringRun) -> str:
    """Publish `scoring_run` to radar-online and return the public report URL.

    Raises:
        DirtyAuditError: the run's audit is dirty; nothing is sent.
        PublishingNotConfiguredError: the online URL or key is not set; nothing is sent.
        PublishFailedError: radar-online answered an error, or the network failed.
    """
    audit = session.get(Audit, scoring_run.audit_id)
    assert audit is not None
    if audit.is_dirty:
        raise DirtyAuditError(
            "The latest audit scored a modified working tree: commit or stash the "
            "changes, audit and score again, then publish"
        )
    base_url, api_key = _online_config()
    body = build_publication_payload(session, scoring_run).model_dump_json().encode()
    request = Request(  # noqa: S310 -- the scheme is checked to be http(s) above
        f"{base_url}/api/reports",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
    )
    try:
        with urlopen(request, timeout=_TIMEOUT_SECONDS) as response:  # noqa: S310
            report_path = json.loads(response.read())["report_path"]
    except HTTPError as exc:
        raise PublishFailedError(
            f"radar-online refused the report ({exc.code}): {_error_detail(exc)}"
        ) from exc
    except URLError as exc:
        raise PublishFailedError(f"radar-online could not be reached: {exc.reason}") from exc
    return f"{base_url}{report_path}"


def _online_config() -> tuple[str, str]:
    base_url = os.environ.get("RADAR_ONLINE_URL", "").strip().rstrip("/")
    api_key = os.environ.get("RADAR_ONLINE_API_KEY", "").strip()
    if not base_url.startswith(("https://", "http://")) or not api_key:
        raise PublishingNotConfiguredError(
            "Set RADAR_ONLINE_URL (http or https) and RADAR_ONLINE_API_KEY to publish"
        )
    return base_url, api_key


def _error_detail(error: HTTPError) -> str:
    try:
        detail = json.loads(error.read())["detail"]
    except ValueError, KeyError, TypeError:
        return str(error.reason)
    if isinstance(detail, list):
        return "; ".join(
            str(item.get("msg", item) if isinstance(item, dict) else item) for item in detail
        )
    return str(detail)
