"""FL Studio MCP: lets Claude compose in FL Studio.

Run it with ``uv run fl-mcp`` (or ``python -m fl_mcp``). That starts the MCP
server on stdio, which is how Claude Desktop talks to it.

stdout is the MCP channel, so nothing in this package prints. The MCP SDK sends
log messages to stderr.
"""


def main() -> None:
    """The opening scene: build the server and serve until the client disconnects."""
    # Imported here so that `import fl_mcp.theory` doesn't load the MCP SDK:
    # the theory layer stays independent of MCP.
    from fl_mcp.server import build_server

    build_server().run()  # stdio is the default transport
