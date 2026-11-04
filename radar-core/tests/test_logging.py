import json
import logging
import re

import pytest
import structlog
from radar_core import observability


@pytest.fixture(autouse=True)
def _reset_logging():
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    yield
    structlog.reset_defaults()
    root.handlers, root.level = handlers, level


def _emit(capsys, **kwargs):
    observability.configure_logging(**kwargs)
    structlog.get_logger().info("audit_started", repo="demo-app", subprojects=2)
    return capsys.readouterr()


def test_writes_json_lines_to_stderr_when_not_a_terminal(capsys, monkeypatch):
    monkeypatch.delenv("RADAR_LOG_FORMAT", raising=False)

    captured = _emit(capsys, is_terminal=False)

    assert captured.out == ""
    line = json.loads(captured.err.strip())
    assert line["event"] == "audit_started"
    assert line["repo"] == "demo-app"
    assert line["level"] == "info"
    assert "timestamp" in line


def test_writes_readable_text_in_a_terminal(capsys, monkeypatch):
    monkeypatch.delenv("RADAR_LOG_FORMAT", raising=False)

    captured = _emit(capsys, is_terminal=True)

    text = re.sub(r"\x1b\[[0-9;]*m", "", captured.err)  # drop terminal colors
    assert "audit_started" in text
    assert "repo=demo-app" in text
    with pytest.raises(json.JSONDecodeError):
        json.loads(text.strip())


def test_format_can_be_forced_through_the_environment(capsys, monkeypatch):
    monkeypatch.setenv("RADAR_LOG_FORMAT", "json")

    captured = _emit(capsys, is_terminal=True)

    assert json.loads(captured.err.strip())["event"] == "audit_started"


def test_level_filters_lower_events(capsys, monkeypatch):
    monkeypatch.setenv("RADAR_LOG_LEVEL", "warning")
    monkeypatch.setenv("RADAR_LOG_FORMAT", "json")

    captured = _emit(capsys, is_terminal=False)

    assert captured.err == ""


def test_bound_context_is_added_to_every_line(capsys, monkeypatch):
    monkeypatch.setenv("RADAR_LOG_FORMAT", "json")
    observability.configure_logging(is_terminal=False)

    with structlog.contextvars.bound_contextvars(audit_id=42):
        structlog.get_logger().info("tool_finished", tool="mypy")

    assert json.loads(capsys.readouterr().err.strip())["audit_id"] == 42


def test_renders_tracebacks_of_standard_library_logs(capsys, monkeypatch):
    monkeypatch.setenv("RADAR_LOG_FORMAT", "json")
    observability.configure_logging(is_terminal=False)

    try:
        raise ValueError("bad value")
    except ValueError:
        # Any third-party library logger (another test may have disabled "sqlalchemy" via alembic).
        logging.getLogger("some_library").exception("query_failed")

    line = json.loads(capsys.readouterr().err.strip())
    assert line["event"] == "query_failed"
    assert "ValueError: bad value" in line["exception"]


def test_configuring_twice_writes_each_line_once_and_keeps_other_handlers(capsys, monkeypatch):
    monkeypatch.setenv("RADAR_LOG_FORMAT", "json")
    other = logging.NullHandler()
    logging.getLogger().addHandler(other)

    observability.configure_logging(is_terminal=False)
    observability.configure_logging(is_terminal=False)
    structlog.get_logger().info("once")

    assert len(capsys.readouterr().err.strip().splitlines()) == 1
    assert other in logging.getLogger().handlers


def test_uvicorn_loggers_go_through_the_structured_handler(capsys, monkeypatch):
    monkeypatch.setenv("RADAR_LOG_FORMAT", "json")
    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.addHandler(logging.StreamHandler())
    uvicorn_error.propagate = False

    observability.configure_logging(is_terminal=False)
    uvicorn_error.info("Application startup complete.")

    assert json.loads(capsys.readouterr().err.strip())["event"] == "Application startup complete."


def test_uvicorn_access_log_is_silenced_since_it_keeps_query_strings(capsys, monkeypatch):
    monkeypatch.setenv("RADAR_LOG_FORMAT", "json")

    observability.configure_logging(is_terminal=False)
    logging.getLogger("uvicorn.access").info('127.0.0.1 - "GET /repositories?token=x HTTP/1.1" 200')

    assert capsys.readouterr().err == ""
