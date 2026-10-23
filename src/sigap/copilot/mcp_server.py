"""Phase 9 · MCP server exposing tools.py, so any MCP client (Claude Desktop, your LangGraph agent,
an IDE) can use the same read-only tools.

Run:  make mcp    (stdio transport)
Docs: https://modelcontextprotocol.io  (Python SDK: `from mcp.server.fastmcp import FastMCP`)

TODO(Agatha) phase 9:
  mcp = FastMCP("sigap")
  @mcp.tool() for each function in tools.py, with a docstring the model can read (what, when to use, parameters)
  if __name__ == "__main__": mcp.run()
"""
