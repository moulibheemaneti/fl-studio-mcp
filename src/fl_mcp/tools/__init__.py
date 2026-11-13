"""Tools: the scenes Claude can step into.

Each tools module is a small, self-contained scene. It exposes one
``register(server)`` function that puts its tools on the MCP server, and it only
translates between MCP and the layers underneath (``theory`` today, the FL
Studio ``bridge`` from Phase 2).

To add tools, write a new module with a ``register`` function and list it in
:data:`TOOLSETS`. The server itself never changes.
"""

from collections.abc import Callable

from mcp.server.mcpserver import MCPServer

from fl_mcp.tools import scales

#: A toolset: something that adds its tools to a server.
RegisterTools = Callable[[MCPServer], None]

#: Every toolset the server loads, in order.
TOOLSETS: tuple[RegisterTools, ...] = (scales.register,)

__all__ = ["TOOLSETS", "RegisterTools"]
