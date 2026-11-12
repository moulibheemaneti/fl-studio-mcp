"""FL Studio MCP server."""

import sys


def main() -> None:
    # stdout is the MCP channel, so anything human-readable goes to stderr.
    print("fl-mcp: the MCP server arrives in Phase 1.", file=sys.stderr)
    raise SystemExit(1)
