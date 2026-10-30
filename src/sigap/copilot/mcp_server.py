"""Phase 9 · MCP server exposing the copilot's read-only tools (tools.py), so any MCP client (Claude Desktop,
an IDE, Hermes Agent) uses exactly the same tools, with the same validation and the same read-only role.

Run:  make mcp    (stdio transport; an MCP client starts this command itself)
Docs: https://modelcontextprotocol.io · Python SDK v2 (`from mcp.server.mcpserver import MCPServer`)

Claude Desktop config (claude_desktop_config.json), absolute paths:
  {"mcpServers": {"sigap": {"command": "/Users/<you>/projects/sigap/.venv/bin/python",
                            "args": ["-m", "sigap.copilot.mcp_server"],
                            "env": {"PYTHONPATH": "/Users/<you>/projects/sigap/src",
                                    "SIGAP_DB_URL": "...", "SIGAP_COPILOT_DB_PASSWORD": "..."}}}}
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from sigap.copilot import tools

INSTRUCTIONS = (
    "Read-only tools over SIGAP, the account-opening fraud system of the fictional Bank Nusa Digital. "
    "Use them to answer analyst questions with numbers from the tools only. None of them can approve, decline "
    "or change anything."
)

server = MCPServer("sigap", instructions=INSTRUCTIONS)
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)
for fn in tools.TOOLS:
    server.tool(annotations=READ_ONLY)(fn)


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
