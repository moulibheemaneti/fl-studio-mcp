"""End to end: start the real server process and talk to it over stdio.

This is exactly how Claude Desktop runs the server. It also proves nothing
pollutes stdout, which would break the MCP channel.
"""

import sys

import pytest
from mcp import Client, StdioServerParameters

pytestmark = pytest.mark.anyio


async def test_server_answers_over_stdio() -> None:
    server_process = StdioServerParameters(command=sys.executable, args=["-m", "fl_mcp"])

    async with Client(server_process) as client:
        tool_names = [tool.name for tool in (await client.list_tools()).tools]
        result = await client.call_tool("get_scale", {"root": "D", "scale": "minor"})

    assert tool_names == ["get_scale"]
    assert result.structured_content["notes"] == ["D", "E", "F", "G", "A", "Bb", "C"]
