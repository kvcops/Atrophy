"""Shared test fixtures for atrophy."""

import pytest
from typer.testing import CliRunner

from atrophy.cli.app import app


@pytest.fixture()
def cli_runner() -> CliRunner:
    """Return a Typer CLI test runner."""
    return CliRunner()


@pytest.fixture()
def invoke(cli_runner: CliRunner):
    """Return a helper that invokes the atrophy CLI."""

    def _invoke(*args: str):
        return cli_runner.invoke(app, list(args))

    return _invoke
