"""Admin command line for radar-online: `radar-online create-account`."""

from __future__ import annotations

from typing import Annotated

import sentry_sdk
import typer
from radar_core.db import get_engine, get_session
from radar_core.observability import configure_logging, init_error_tracking

from radar_online.accounts import AccountCreationError, create_active_account
from radar_online.config import get_database_url

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Administer radar-online accounts."""


@app.command("create-account")
def create_account(
    email: Annotated[str, typer.Option(help="Owner's email address")],
    display_name: Annotated[str, typer.Option(help="Public name, 1 to 100 characters")],
    slug: Annotated[str, typer.Option(help="Public namespace: lowercase letters, digits, -")],
) -> None:
    """Create an active account and print its first API key, shown once."""
    engine = get_engine(get_database_url())
    session = get_session(engine)
    try:
        key = create_active_account(session, email=email, display_name=display_name, slug=slug)
    except AccountCreationError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    finally:
        session.close()
        engine.dispose()
    typer.echo(f"Account {slug!r} created. API key (shown once, store it now):")
    typer.echo(key)


def entrypoint() -> None:
    """Console-script entry point: run the CLI, reporting unexpected crashes to Sentry."""
    configure_logging()
    init_error_tracking()
    try:
        app()
    # Typer swaps sys.excepthook on every call, so Sentry's own hook never fires.
    except Exception:
        sentry_sdk.capture_exception()
        raise
