import pytest
from radar_core.db import get_engine, get_session, persisted_id
from radar_core.enums import ScoringModel
from radar_core.models.methodology import Criterion, MethodologyVersion
from sqlalchemy.exc import IntegrityError


def test_sqlite_foreign_keys_are_enforced(db_session):
    orphan_criterion = Criterion(
        category_id=999_999,
        name="Orphan criterion",
        description="References a category_id that does not exist",
        weight=1.0,
        scoring_model=ScoringModel.FIXED_SCALE,
    )
    db_session.add(orphan_criterion)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_get_engine_binds_to_given_url(tmp_path):
    db_path = tmp_path / "engine_test.db"
    engine = get_engine(f"sqlite:///{db_path}")

    assert str(engine.url) == f"sqlite:///{db_path}"


def test_two_engines_on_different_urls_are_independent(tmp_path):
    engine_a = get_engine(f"sqlite:///{tmp_path / 'a.db'}")
    engine_b = get_engine(f"sqlite:///{tmp_path / 'b.db'}")

    assert engine_a.url != engine_b.url


def test_get_session_returns_open_session(tmp_path):
    engine = get_engine(f"sqlite:///{tmp_path / 'session_test.db'}")

    session = get_session(engine)
    try:
        assert session.is_active
    finally:
        session.close()


def test_persisted_id_returns_the_id_of_a_flushed_row(db_session):
    version = MethodologyVersion(version_label="persisted-id-test")
    db_session.add(version)
    db_session.flush()

    assert persisted_id(version) == version.id


def test_persisted_id_rejects_an_unsaved_row():
    with pytest.raises(ValueError, match="MethodologyVersion"):
        persisted_id(MethodologyVersion(version_label="never-flushed"))
