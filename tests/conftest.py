"""Shared test setup."""

import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests on asyncio, the event loop the MCP SDK uses in production."""
    return "asyncio"
