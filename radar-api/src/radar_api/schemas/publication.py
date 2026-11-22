"""Pydantic schema for the publish preview response."""

from __future__ import annotations

from pydantic import BaseModel
from radar_core.publication import PublicationPayload


class PublishPreview(BaseModel):
    """The exact payload a publication would send, and whether its audit was dirty.

    A dirty audit scored a modified working tree, so its commit does not describe the
    scored code exactly: shown here, refused at publication time.
    """

    is_dirty: bool
    payload: PublicationPayload


class PublishResult(BaseModel):
    """Where the published report can be seen on radar-online."""

    report_url: str
