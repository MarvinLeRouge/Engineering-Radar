from datetime import UTC, datetime

import pytest
from radar_core.enums import (
    Confidence,
    FindingSeverity,
    HumanVerdict,
    ScoreLevel,
    ScoringModel,
)
from radar_core.models.audit import Audit
from radar_core.models.finding import Finding, Recommendation
from radar_core.models.methodology import Category, Criterion, MethodologyVersion
from radar_core.models.repository import Repository
from radar_core.models.scoring import Score, ScoringRun
from radar_core.publication_builder import build_publication_payload, repository_slug

_ROOT_KEYS = {
    "schema_version",
    "repository",
    "commit_sha",
    "scored_at",
    "methodology_version",
    "global_score",
    "categories",
}
_CATEGORY_KEYS = {"name", "order", "weight", "status", "implemented", "value", "confidence"}


def _add(session, row):
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def _category(session, version, name, order, weight, implemented):
    category = _add(
        session, Category(methodology_version_id=version.id, name=name, weight=weight, order=order)
    )
    criterion = _add(
        session,
        Criterion(
            category_id=category.id,
            name=f"{name} criterion",
            description="secret criterion description",
            weight=1.0,
            scoring_model=ScoringModel.FIXED_SCALE,
            implemented=implemented,
        ),
    )
    return category, criterion


@pytest.fixture
def scoring_run(db_session):
    repository = _add(db_session, Repository(name="Summit-Stats", path="/home/me/Summit-Stats"))
    audit = _add(db_session, Audit(repository_id=repository.id, commit_sha="c" * 40))
    version = _add(db_session, MethodologyVersion(version_label="Quality Framework v1.0"))
    run = _add(
        db_session,
        ScoringRun(
            audit_id=audit.id,
            methodology_version_id=version.id,
            global_score=7.4,
            scored_at=datetime(2026, 11, 5, 14, 20, tzinfo=UTC),
        ),
    )
    security, criterion = _category(db_session, version, "Security", 4, 1.5, implemented=True)
    _category(db_session, version, "Testing", 2, 2.0, implemented=True)
    _category(db_session, version, "Performance", 6, 1.0, implemented=False)
    _add(
        db_session,
        Score(
            scoring_run_id=run.id,
            category_id=security.id,
            level=ScoreLevel.CATEGORY,
            value=6.2,
            confidence=Confidence.HIGH,
        ),
    )
    _add(
        db_session,
        Score(
            scoring_run_id=run.id,
            criterion_id=criterion.id,
            level=ScoreLevel.CRITERION,
            value=6.2,
            confidence=Confidence.HIGH,
        ),
    )
    finding = _add(
        db_session,
        Finding(
            scoring_run_id=run.id,
            criterion_id=criterion.id,
            severity=FindingSeverity.HIGH,
            confidence=Confidence.HIGH,
            description="secret finding description",
            file="app/secret_path.py",
            line=42,
            human_verdict=HumanVerdict.FALSE_POSITIVE,
            verdict_note="secret verdict note",
        ),
    )
    _add(db_session, Recommendation(finding_id=finding.id, text="secret recommendation"))
    return run


def test_payload_holds_only_the_contract_fields(db_session, scoring_run):
    payload = build_publication_payload(db_session, scoring_run).model_dump(mode="json")

    assert set(payload) == _ROOT_KEYS
    assert set(payload["repository"]) == {"slug", "display_name"}
    assert all(set(category) == _CATEGORY_KEYS for category in payload["categories"])


def test_no_local_detail_leaves_in_the_payload(db_session, scoring_run):
    serialized = build_publication_payload(db_session, scoring_run).model_dump_json()

    for leaked in ("secret", "/home/me", "app/", "criterion", "42"):
        assert leaked not in serialized


def test_payload_maps_the_scoring_run(db_session, scoring_run):
    payload = build_publication_payload(db_session, scoring_run)

    assert payload.schema_version == 1
    assert (payload.repository.slug, payload.repository.display_name) == (
        "summit-stats",
        "Summit-Stats",
    )
    assert payload.commit_sha == "c" * 40
    assert payload.scored_at == datetime(2026, 11, 5, 14, 20, tzinfo=UTC)
    assert payload.methodology_version == "Quality Framework v1.0"
    assert payload.global_score == 7.4


def test_categories_follow_the_taxonomy_order_with_their_status(db_session, scoring_run):
    categories = build_publication_payload(db_session, scoring_run).categories

    assert [(c.name, c.order, c.weight) for c in categories] == [
        ("Testing", 2, 2.0),
        ("Security", 4, 1.5),
        ("Performance", 6, 1.0),
    ]
    testing, security, performance = categories
    assert (security.status, security.implemented, security.value, security.confidence) == (
        "scored",
        True,
        6.2,
        Confidence.HIGH,
    )
    assert (testing.status, testing.implemented, testing.value) == ("not_yet_audited", True, None)
    assert (performance.status, performance.implemented, performance.value) == (
        "not_yet_audited",
        False,
        None,
    )


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        ("Summit-Stats", "summit-stats"),
        ("Portfolio Engineering_Radar", "portfolio-engineering-radar"),
        ("-geo_data-", "geo-data"),
        ("HiveMind", "hivemind"),
    ],
)
def test_repository_slug_is_derived_from_the_local_name(name, slug):
    assert repository_slug(name) == slug
