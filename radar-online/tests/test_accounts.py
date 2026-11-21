import pytest
from radar_online.accounts import AccountCreationError, create_active_account
from radar_online.models import ApiKey, User, UserStatus
from radar_online.tokens import hash_secret
from sqlmodel import select


def _create(session, email="ada@example.com", display_name="Ada", slug="ada"):
    return create_active_account(session, email=email, display_name=display_name, slug=slug)


def test_creates_an_active_user_with_one_hashed_api_key(session):
    key = _create(session)

    user = session.exec(select(User)).one()
    api_key = session.exec(select(ApiKey)).one()
    assert user.status == UserStatus.ACTIVE
    assert user.approved_at is not None
    assert (user.email, user.display_name, user.slug) == ("ada@example.com", "Ada", "ada")
    assert api_key.user_id == user.id
    assert api_key.key_hash == hash_secret(key)
    assert api_key.prefix == key[:8]
    assert api_key.revoked_at is None


def test_plain_key_is_never_stored(session):
    key = _create(session)

    api_key = session.exec(select(ApiKey)).one()
    assert key not in api_key.model_dump().values()


def test_duplicate_email_is_rejected_whatever_its_case(session):
    _create(session)

    with pytest.raises(AccountCreationError, match="email"):
        _create(session, email="  ADA@Example.com", slug="other")

    assert len(session.exec(select(User)).all()) == 1


def test_duplicate_slug_is_rejected(session):
    _create(session)

    with pytest.raises(AccountCreationError, match="slug"):
        _create(session, email="bob@example.com")

    assert len(session.exec(select(ApiKey)).all()) == 1


@pytest.mark.parametrize("slug", ["", "Ada", "ada lovelace", "ada_l", "a" * 65])
def test_invalid_slug_is_rejected(session, slug):
    with pytest.raises(AccountCreationError, match="slug"):
        _create(session, slug=slug)


@pytest.mark.parametrize("display_name", ["", "   ", "a" * 101, "Ada\nLovelace", "<b>Ada</b>"])
def test_invalid_display_name_is_rejected(session, display_name):
    with pytest.raises(AccountCreationError, match="display name"):
        _create(session, display_name=display_name)


@pytest.mark.parametrize("email", ["", "ada.example.com", "a" * 250 + "@x.io"])
def test_invalid_email_is_rejected(session, email):
    with pytest.raises(AccountCreationError, match="email"):
        _create(session, email=email)
