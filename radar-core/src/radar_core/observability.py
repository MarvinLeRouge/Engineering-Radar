"""Error tracking (Sentry) and structured logging setup shared by radar-api and radar-audit."""

from __future__ import annotations

import logging
import os
import sys
from typing import TYPE_CHECKING

import sentry_sdk
import structlog

if TYPE_CHECKING:
    from sentry_sdk._types import DataCollectionUserOptions

SENTRY_DATA_COLLECTION: DataCollectionUserOptions = {
    "user_info": False,
    "cookies": {"mode": "off"},
    "http_headers": {"request": {"mode": "off"}},
    "http_bodies": [],
    "url_query_params": {"mode": "off"},
    "graphql": {"document": False, "variables": False},
    "gen_ai": {"inputs": False, "outputs": False},
    "database_query_data": False,
    "queues": False,
    "stack_frame_variables": False,
    "frame_context_lines": 0,
}


def init_error_tracking() -> bool:
    """Initialize Sentry when a DSN is configured.

    Returns:
        True if Sentry was initialized, False if it is disabled.
    """
    dsn = os.environ.get("SENTRY_DSN", "").strip()

    if not dsn:
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "").strip() or "development",
        data_collection=SENTRY_DATA_COLLECTION,
        traces_sample_rate=0.0,
    )

    return True


_HANDLER_MARKER = "_radar_structured_logging"
_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error")


def configure_logging(is_terminal: bool | None = None) -> None:
    """Route structured logs to stderr, as JSON lines or as readable text.

    Format: RADAR_LOG_FORMAT ("json" or "console"), else JSON unless stderr is a
    terminal. Level: RADAR_LOG_LEVEL (default "info"). Logs go through the standard
    logging module, so Sentry's logging integration attaches recent ones to errors.
    stdout stays free for the CLI's own output (plans, reports).
    """
    if is_terminal is None:
        is_terminal = sys.stderr.isatty()
    log_format = os.environ.get("RADAR_LOG_FORMAT", "").strip().lower()
    as_json = log_format == "json" or (log_format != "console" and not is_terminal)
    level = logging.getLevelNamesMapping().get(
        os.environ.get("RADAR_LOG_LEVEL", "").strip().upper(), logging.INFO
    )

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if as_json
        else structlog.dev.ConsoleRenderer(colors=is_terminal)
    )
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                # Standard-library records (SQLAlchemy, uvicorn) carry raw exc_info.
                structlog.processors.format_exc_info,
                renderer,
            ],
        )
    )
    setattr(handler, _HANDLER_MARKER, True)
    root = logging.getLogger()
    # Replace only the handler this function installed, so calling it twice never doubles lines.
    root.handlers = [h for h in root.handlers if not getattr(h, _HANDLER_MARKER, False)]
    root.addHandler(handler)
    root.setLevel(level)
    # uvicorn installs its own plain-text handlers and stops propagation: route them here.
    for name in _UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
    # radar-api logs each request itself, without the query string uvicorn's access log keeps.
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers.clear()
    access_logger.propagate = False

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
