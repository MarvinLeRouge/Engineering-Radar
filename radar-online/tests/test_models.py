from datetime import UTC, datetime, timedelta

import pytest
from radar_online.models import (
    ActionToken,
    ActionTokenPurpose,
    ApiKey,
    PublishedReport,
    PublishedRepository,
    User,
    UserStatus,
)
from sqlalchemy.exc import IntegrityError
from sqlmodel import select


def _user(session, email="ada@example.com", slug="ada"):
    user = User(email=email, display_name="Ada", slug=slug)
    session.add(user)
    session.commit()
    return user


def _repository(session, user, slug="summit-stats"):
    repository = PublishedRepository(user_id=user.id, slug=slug, display_name="Summit-Stats")
    session.add(repository)
    session.commit()
    return repository


def _report(repository, commit_sha="a" * 40):
    return PublishedReport(
        repository_id=repository.id,
        commit_sha=commit_sha,
        scored_at=datetime(2026, 11, 5, tzinfo=UTC),
        methodology_version="1.0",
        schema_version=1,
        global_score=7.4,
        payload={"global_score": 7.4},
    )


def test_a_new_user_waits_for_email_confirmation(session):
    user = _user(session)

    assert user.status == UserStatus.PENDING_EMAIL
    assert user.created_at.tzinfo is not None


def test_emails_are_stored_lowercase_and_unique(session):
    _user(session, email="Ada@Example.com")

    assert session.exec(select(User)).one().email == "ada@example.com"
    with pytest.raises(IntegrityError):
        _user(session, email="ADA@example.com", slug="other")


def test_public_slugs_are_unique(session):
    _user(session)

    with pytest.raises(IntegrityError):
        _user(session, email="other@example.com")


def test_a_repository_slug_is_unique_per_user_only(session):
    ada = _user(session)
    bob = _user(session, email="bob@example.com", slug="bob")
    _repository(session, ada)
    _repository(session, bob)

    with pytest.raises(IntegrityError):
        _repository(session, ada)


def test_one_report_per_repository_and_commit(session):
    repository = _repository(session, _user(session))
    session.add(_report(repository))
    session.add(_report(repository, commit_sha="b" * 40))
    session.commit()

    session.add(_report(repository))
    with pytest.raises(IntegrityError):
        session.commit()


def test_the_report_payload_round_trips_as_json(session):
    repository = _repository(session, _user(session))
    session.add(_report(repository))
    session.commit()
    session.expire_all()

    assert session.exec(select(PublishedReport)).one().payload == {"global_score": 7.4}


def test_key_and_token_hashes_are_unique(session):
    user = _user(session)
    session.add(ApiKey(user_id=user.id, prefix="abcd1234", key_hash="h" * 64))
    session.add(
        ActionToken(
            user_id=user.id,
            purpose=ActionTokenPurpose.CONFIRM_EMAIL,
            token_hash="t" * 64,
            expires_at=datetime.now(UTC) + timedelta(hours=48),
        )
    )
    session.commit()

    session.add(ApiKey(user_id=user.id, prefix="abcd1234", key_hash="h" * 64))
    with pytest.raises(IntegrityError):
        session.commit()


def test_deleting_a_user_deletes_all_their_data(session):
    user = _user(session)
    other = _user(session, email="bob@example.com", slug="bob")
    repository = _repository(session, user)
    session.add(_report(repository))
    session.add(ApiKey(user_id=user.id, prefix="abcd1234", key_hash="h" * 64))
    session.add(
        ActionToken(
            user_id=user.id,
            purpose=ActionTokenPurpose.REVEAL_KEY,
            token_hash="t" * 64,
            expires_at=datetime.now(UTC),
        )
    )
    _repository(session, other)
    session.commit()

    session.delete(user)
    session.commit()

    assert session.exec(select(PublishedReport)).all() == []
    assert session.exec(select(ApiKey)).all() == []
    assert session.exec(select(ActionToken)).all() == []
    assert [r.user_id for r in session.exec(select(PublishedRepository))] == [other.id]


def test_an_email_lookup_ignores_case(session):
    _user(session, email="ada@example.com")

    assert session.exec(select(User).where(User.email == " ADA@Example.COM")).one().slug == "ada"
