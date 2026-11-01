"""Stable group keys for improvement tasks, so they can be upserted across re-scoring runs."""

from __future__ import annotations

import hashlib

_GROUP_KEY_LENGTH = 16


def compute_task_group_key(
    criterion_id: int, file: str | None, atomic_finding_fingerprint: str | None = None
) -> str:
    """Compute a stable identifier for an `ImprovementTask`'s grouping, so it
    can be upserted instead of deleted and recreated on every re-score.

    For an atomic task (one criterion/file whose findings bypass grouping
    entirely, e.g. dependency circularity or code duplication), the caller
    passes the single underlying Finding's own fingerprint, reused verbatim --
    it is already a stable per-instance identifier, see
    radar_core.finding_fingerprint. Otherwise the key is derived from
    (criterion_id, file), matching compute_fingerprint's repr()-of-a-tuple
    approach to avoid a field-boundary collision.
    """
    if atomic_finding_fingerprint is not None:
        return atomic_finding_fingerprint
    key = repr((criterion_id, file))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:_GROUP_KEY_LENGTH]
