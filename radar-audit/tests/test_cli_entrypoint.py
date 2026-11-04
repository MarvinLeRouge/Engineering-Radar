"""Tests for the Sentry-aware radar-audit console entry point."""

import pytest
import sentry_sdk
from radar_audit import cli
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport


@pytest.fixture
def captured_events(monkeypatch):
    envelopes: list[Envelope] = []

    class MemoryTransport(Transport):
        def capture_envelope(self, envelope: Envelope) -> None:
            envelopes.append(envelope)

    monkeypatch.setattr(
        cli,
        "init_error_tracking",
        lambda: sentry_sdk.init(dsn="http://public@example.com/1", transport=MemoryTransport),
    )
    yield lambda: [event for e in envelopes if (event := e.get_event()) is not None]
    sentry_sdk.init(dsn="")


def test_unexpected_crash_is_reported_and_reraised(monkeypatch, captured_events):
    """An unhandled exception escaping the CLI must reach Sentry and still propagate."""

    def crashing_app():
        raise RuntimeError("Expected radar-audit Sentry test exception")

    monkeypatch.setattr(cli, "app", crashing_app)

    with pytest.raises(RuntimeError):
        cli.entrypoint()
    sentry_sdk.flush(timeout=2)

    events = captured_events()
    assert len(events) == 1
    assert events[0]["exception"]["values"][0]["type"] == "RuntimeError"


def test_normal_exit_is_not_reported(monkeypatch, captured_events):
    """A CLI exit (success or handled error) must not produce a Sentry event."""

    def exiting_app():
        raise SystemExit(1)

    monkeypatch.setattr(cli, "app", exiting_app)

    with pytest.raises(SystemExit):
        cli.entrypoint()
    sentry_sdk.flush(timeout=2)

    assert captured_events() == []


def test_entrypoint_configures_logging_before_running(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "configure_logging", lambda: calls.append("logging"))
    monkeypatch.setattr(cli, "init_error_tracking", lambda: calls.append("sentry"))
    monkeypatch.setattr(cli, "app", lambda: calls.append("app"))

    cli.entrypoint()

    assert calls == ["logging", "sentry", "app"]
