from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from radar_core.publication import PublicationPayload


def _category(**overrides):
    return {
        "name": "Security",
        "order": 4,
        "weight": 1.5,
        "status": "scored",
        "implemented": True,
        "value": 6.2,
        "confidence": "HIGH",
        **overrides,
    }


def _payload(**overrides):
    return {
        "schema_version": 1,
        "repository": {"slug": "summit-stats", "display_name": "Summit-Stats"},
        "commit_sha": "a" * 40,
        "scored_at": "2026-11-05T14:20:00Z",
        "methodology_version": "1.0",
        "global_score": 7.4,
        "categories": [_category()],
        **overrides,
    }


def test_a_valid_payload_is_accepted():
    payload = PublicationPayload.model_validate(_payload())

    assert payload.repository.slug == "summit-stats"
    assert payload.scored_at == datetime(2026, 11, 5, 14, 20, tzinfo=UTC)
    assert payload.categories[0].value == 6.2


def test_a_json_round_trip_gives_the_same_payload():
    payload = PublicationPayload.model_validate(_payload())

    assert PublicationPayload.model_validate_json(payload.model_dump_json()) == payload


@pytest.mark.parametrize(
    "payload",
    [
        _payload(findings=[]),
        _payload(repository={"slug": "x", "display_name": "X", "path": "/home/me/x"}),
        _payload(categories=[_category(criteria=[])]),
    ],
    ids=["top-level", "repository", "category"],
)
def test_unknown_fields_are_rejected_at_every_level(payload):
    # A newer local version must never leak a field an older server would store (ADR 0014).
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PublicationPayload.model_validate(payload)


@pytest.mark.parametrize(
    "overrides",
    [
        {"schema_version": 2},
        {"repository": {"slug": "Summit Stats", "display_name": "x"}},
        {"repository": {"slug": "", "display_name": "x"}},
        {"repository": {"slug": "a" * 65, "display_name": "x"}},
        {"repository": {"slug": "-leading", "display_name": "x"}},
        {"repository": {"slug": "ok", "display_name": ""}},
        {"repository": {"slug": "ok", "display_name": "x" * 101}},
        {"commit_sha": "abc"},
        {"commit_sha": "g" * 40},
        {"scored_at": "2026-11-05T14:20:00"},
        {"methodology_version": ""},
        {"global_score": 10.5},
        {"global_score": -1},
        {"categories": []},
        {"categories": [_category(name=f"c{i}", order=i) for i in range(31)]},
        {"repository": {"slug": "ok", "display_name": "<script>alert(1)</script>"}},
        {"repository": {"slug": "ok", "display_name": "two\nlines"}},
        {"methodology_version": "v1\u0000"},
        {"global_score": float("nan")},
        {"categories": [_category(), _category(order=5)]},
        {"categories": [_category(), _category(name="Code quality")]},
        {
            "global_score": 5.0,
            "categories": [_category(status="not_yet_audited", value=None, implemented=False)],
        },
    ],
    ids=[
        "schema-version",
        "slug-spaces",
        "slug-empty",
        "slug-too-long",
        "slug-leading-hyphen",
        "name-empty",
        "name-too-long",
        "sha-short",
        "sha-not-hex",
        "naive-datetime",
        "methodology-empty",
        "score-above-10",
        "score-negative",
        "no-category",
        "too-many-categories",
        "markup-in-name",
        "newline-in-name",
        "control-char-in-version",
        "nan-score",
        "duplicate-category-name",
        "duplicate-category-order",
        "global-score-without-scored-category",
    ],
)
def test_invalid_payload_fields_are_rejected(overrides):
    with pytest.raises(ValidationError):
        PublicationPayload.model_validate(_payload(**overrides))


@pytest.mark.parametrize(
    "category",
    [
        _category(value=11),
        _category(status="not_applicable"),
        _category(implemented=False),
        _category(status="not_yet_audited", value=5.0),
        _category(confidence="VERY HIGH"),
        _category(weight=float("inf")),
        _category(weight=101),
        _category(name="Security\t"),
    ],
    ids=[
        "value-above-10",
        "unknown-status",
        "unimplemented-with-value",
        "unscored-with-value",
        "unknown-confidence",
        "infinite-weight",
        "weight-above-100",
        "control-char-in-name",
    ],
)
def test_invalid_categories_are_rejected(category):
    with pytest.raises(ValidationError):
        PublicationPayload.model_validate(_payload(categories=[category]))


def test_unimplemented_and_unscored_categories_carry_no_value():
    payload = PublicationPayload.model_validate(
        _payload(
            categories=[
                _category(),
                _category(
                    name="Performance",
                    order=6,
                    status="not_yet_audited",
                    value=None,
                    implemented=False,
                    confidence=None,
                ),
            ]
        )
    )

    assert payload.categories[1].value is None


def test_a_null_global_score_is_accepted():
    assert PublicationPayload.model_validate(_payload(global_score=None)).global_score is None


def test_real_taxonomy_labels_are_accepted():
    payload = PublicationPayload.model_validate(
        _payload(
            methodology_version="Quality Framework v1.0",
            categories=[_category(name="Architecture & design", order=1), _category(order=4)],
        )
    )

    assert payload.categories[0].name == "Architecture & design"


def test_a_utc_offset_is_kept_as_the_same_instant():
    payload = PublicationPayload.model_validate(_payload(scored_at="2026-11-05T16:20:00+02:00"))

    assert payload.scored_at == datetime(2026, 11, 5, 14, 20, tzinfo=UTC)
