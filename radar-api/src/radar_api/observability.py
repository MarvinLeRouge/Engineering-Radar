"""Application observability and error tracking configuration."""

from __future__ import annotations

import os

import sentry_sdk

SENTRY_DATA_COLLECTION = {
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

    environment = os.environ.get("SENTRY_ENVIRONMENT", "development").strip()
    if not environment:
        environment = "development"

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        data_collection=SENTRY_DATA_COLLECTION,
        traces_sample_rate=0.0,
    )

    return True
