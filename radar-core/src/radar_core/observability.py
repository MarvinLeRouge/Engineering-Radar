"""Sentry error tracking setup shared by radar-api and radar-audit."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import sentry_sdk

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
