"""HTTP middleware writing one structured log line per request, shared by every API."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

import structlog

log = structlog.get_logger("radar.requests")


class _Url(Protocol):
    path: str


class _Request(Protocol):
    method: str
    url: _Url
    scope: dict[str, Any]


class _Response(Protocol):
    status_code: int


async def log_requests[ResponseT: _Response](
    request: _Request, call_next: Callable[[Any], Awaitable[ResponseT]]
) -> ResponseT:
    """Log method, route, status and duration; never the query string, headers or body.

    The route is the matched path template (`/api/reviews/{token}`), so an identifier
    or a secret carried in a path never reaches the logs; an unmatched request keeps
    its raw path. Typed structurally so radar-core needs no web framework.
    """
    start = time.monotonic()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        log.log(
            logging.ERROR if status >= 500 else logging.INFO,
            "request_handled",
            method=request.method,
            path=_route_template(request),
            status=status,
            duration_ms=int((time.monotonic() - start) * 1000),
        )


def _route_template(request: _Request) -> str:
    """Return the matched route template, or the raw path when nothing matched.

    A route of a nested router only knows its own part (`/users/{user_slug}`), so the
    router prefixes are taken back from the leading segments of the actual path:
    prefixes are literal and each parameter fills exactly one segment.
    """
    path = request.url.path
    route_path = getattr(request.scope.get("route"), "path", None)
    if not route_path:
        return path
    path_segments = path.rstrip("/").split("/")
    route_segments = route_path.rstrip("/").split("/")[1:]
    prefix = path_segments[: len(path_segments) - len(route_segments)]
    return "/".join([*prefix, *route_segments]) or "/"
