"""Unit tests for the shared Sentry error tracking setup."""

from unittest.mock import Mock

from radar_core import observability


def test_init_error_tracking_without_dsn(monkeypatch):
    """Sentry must remain disabled when no DSN is configured."""
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    init_mock = Mock()
    monkeypatch.setattr(observability.sentry_sdk, "init", init_mock)

    assert observability.init_error_tracking() is False
    init_mock.assert_not_called()


def test_init_error_tracking_with_blank_dsn(monkeypatch):
    """Sentry must remain disabled when the DSN is blank."""
    monkeypatch.setenv("SENTRY_DSN", "   ")
    init_mock = Mock()
    monkeypatch.setattr(observability.sentry_sdk, "init", init_mock)

    assert observability.init_error_tracking() is False
    init_mock.assert_not_called()


def test_init_error_tracking_uses_development_environment_by_default(monkeypatch):
    """Sentry must default to development when no environment is configured."""
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/123")
    monkeypatch.delenv("SENTRY_ENVIRONMENT", raising=False)
    init_mock = Mock()
    monkeypatch.setattr(observability.sentry_sdk, "init", init_mock)

    assert observability.init_error_tracking() is True

    init_mock.assert_called_once_with(
        dsn="https://example@sentry.io/123",
        environment="development",
        data_collection=observability.SENTRY_DATA_COLLECTION,
        traces_sample_rate=0.0,
        before_send=observability.scrub_request,
    )


def test_init_error_tracking_uses_configured_environment(monkeypatch):
    """Sentry must use stripped DSN and environment values."""
    monkeypatch.setenv("SENTRY_DSN", " https://example@sentry.io/123 ")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", " staging ")
    init_mock = Mock()
    monkeypatch.setattr(observability.sentry_sdk, "init", init_mock)

    assert observability.init_error_tracking() is True

    init_mock.assert_called_once_with(
        dsn="https://example@sentry.io/123",
        environment="staging",
        data_collection=observability.SENTRY_DATA_COLLECTION,
        traces_sample_rate=0.0,
        before_send=observability.scrub_request,
    )


def test_init_error_tracking_with_blank_environment(monkeypatch):
    """Sentry must default to development when the environment is blank."""
    monkeypatch.setenv("SENTRY_DSN", "https://example@sentry.io/123")
    monkeypatch.setenv("SENTRY_ENVIRONMENT", "   ")
    init_mock = Mock()
    monkeypatch.setattr(observability.sentry_sdk, "init", init_mock)

    assert observability.init_error_tracking() is True

    init_mock.assert_called_once_with(
        dsn="https://example@sentry.io/123",
        environment="development",
        data_collection=observability.SENTRY_DATA_COLLECTION,
        traces_sample_rate=0.0,
        before_send=observability.scrub_request,
    )


def test_events_never_carry_the_request_url_headers_or_body():
    """A key in a header or a token in a path must not reach Sentry, whatever the SDK collects."""
    event = {
        "message": "boom",
        "request": {
            "url": "https://radar.example.dev/api/reviews/secret-token",
            "method": "POST",
            "query_string": "token=secret-token",
            "headers": {"X-API-Key": "secret-key"},
            "data": {"key": "secret-key"},
            "cookies": {"session": "secret"},
        },
    }

    scrubbed = observability.scrub_request(event, {})

    assert scrubbed is not None
    assert scrubbed["request"] == {"method": "POST"}
    assert "secret" not in str(scrubbed)
    assert scrubbed["message"] == "boom"


def test_events_without_a_request_pass_unchanged():
    event = {"message": "boom"}

    assert observability.scrub_request(event, {}) == {"message": "boom"}
