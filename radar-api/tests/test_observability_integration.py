"""Integration tests for Sentry error capture in FastAPI."""

import sentry_sdk
from fastapi import FastAPI
from fastapi.testclient import TestClient
from radar_core.observability import SENTRY_DATA_COLLECTION
from sentry_sdk.envelope import Envelope
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.transport import Transport


def test_fastapi_unhandled_exception_is_captured():
    """An unhandled FastAPI exception must produce a Sentry event."""
    captured_envelopes: list[Envelope] = []

    class MemoryTransport(Transport):
        def capture_envelope(self, envelope: Envelope) -> None:
            captured_envelopes.append(envelope)

    sentry_sdk.init(
        dsn="http://public@example.com/1",
        transport=MemoryTransport,
        integrations=[FastApiIntegration()],
        data_collection=SENTRY_DATA_COLLECTION,
        traces_sample_rate=0.0,
    )

    app = FastAPI()

    @app.get("/test-error")
    async def trigger_error():
        raise RuntimeError("Expected Sentry integration test exception")

    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            response = client.get(
                "/test-error?secret_query=query-value",
                headers={
                    "Authorization": "Bearer secret-token",
                    "Cookie": "session_id=secret-cookie",
                },
            )
        assert response.status_code == 500

        sentry_sdk.flush(timeout=2)

        events = [
            event for envelope in captured_envelopes if (event := envelope.get_event()) is not None
        ]

        assert len(events) >= 1

        event_content = repr(events[0])
        assert "query-value" not in event_content
        assert "secret-token" not in event_content
        assert "secret-cookie" not in event_content

        exception_values = events[0]["exception"]["values"]
        assert exception_values[0]["type"] == "RuntimeError"
        assert exception_values[0]["value"] == "Expected Sentry integration test exception"
    finally:
        sentry_sdk.flush(timeout=2)
        sentry_sdk.init(dsn="")
