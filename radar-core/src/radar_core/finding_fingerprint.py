"""Stable fingerprints identifying the same underlying finding across re-audits."""

from __future__ import annotations

import hashlib

from radar_core.enums import FindingSeverity

_FINGERPRINT_LENGTH = 16


def compute_fingerprint(
    criterion_id: int | None, severity: FindingSeverity, file: str | None, label: str
) -> str:
    """Compute a stable identifier for "the same underlying issue" across
    re-audits of the same repository.

    Deliberately excludes the line number (shifts when unrelated code is
    added/removed elsewhere in the file) and the raw, human-displayed
    description (often embeds volatile data like an exact LOC count or a
    cyclomatic complexity value). `label` is a normalized, non-volatile
    stand-in built by the caller -- see
    docs/work-in-progress/finding-fingerprint-design.md for the per-criterion
    survey of what each normalizer uses as its label.
    """
    # repr() of a tuple quotes and escapes each string component, so a `|` (or
    # any other character) occurring inside `file` or `label` can never shift
    # a character across the field boundary and collide with a different
    # (file, label) pair -- unlike a plain "|"-joined format string.
    key = repr((criterion_id, severity.value, file, label))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:_FINGERPRINT_LENGTH]
