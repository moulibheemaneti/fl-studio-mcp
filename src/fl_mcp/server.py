"""The stage: where the MCP server is built and every tool takes its place.

The story of one request (Phase 1):
    1. Claude Desktop starts ``fl-mcp``, which builds this server and talks to
       it over stdio.
    2. Claude asks which tools exist; the server lists ``get_scale``.
    3. Claude calls ``get_scale``. The tool (``tools/scales.py``) passes the
       request to the theory (``theory/scales.py``), which builds and spells
       the scale.
    4. The tool answers with a short sentence plus structured data.

This module only assembles the cast. It knows the server's identity and which
toolsets to load, and nothing about music or FL Studio.
"""

from __future__ import annotations

from collections.abc import Iterable
from importlib.metadata import version

from mcp.server.mcpserver import MCPServer

from fl_mcp.tools import TOOLSETS, RegisterTools

#: The server's name, as MCP clients identify it.
SERVER_NAME = "fl-studio"

#: A human-friendly title for client UIs.
SERVER_TITLE = "FL Studio"

#: The package whose version the server reports (from pyproject.toml).
PACKAGE_NAME = "fl-mcp"

#: What the server is for and how to use it, sent to clients when they connect.
SERVER_INSTRUCTIONS = (
    "Tools for composing music in FL Studio. FL Studio names octaves differently from "
    "most references: MIDI 60 is C5 in FL Studio, not C4. For any question about the "
    "notes of a key or scale, call get_scale instead of answering from memory, so note "
    "names and MIDI numbers match FL Studio. This version provides music theory "
    "(scales); controlling FL Studio itself comes in later versions."
)


def build_server(toolsets: Iterable[RegisterTools] = TOOLSETS) -> MCPServer:
    """Create the MCP server and let every toolset register its tools.

    Args:
        toolsets: The toolsets to load. Defaults to every toolset in
            :data:`fl_mcp.tools.TOOLSETS`; tests can pass their own.
    """
    server = MCPServer(
        name=SERVER_NAME,
        title=SERVER_TITLE,
        version=version(PACKAGE_NAME),
        instructions=SERVER_INSTRUCTIONS,
    )
    for register in toolsets:
        register(server)  # each toolset adds its own tools
    return server
