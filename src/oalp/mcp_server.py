"""OALP as an MCP server, so any MCP-capable agent or host can commit and query decisions.

Run:  oalp-mcp            (stdio transport; repository in the current directory)
      OALP_ROOT=/path oalp-mcp
"""

from __future__ import annotations

import os

from .core import OALPError, Repository

try:  # MCP Python SDK 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:
    try:  # MCP Python SDK 1.x
        from mcp.server.fastmcp import FastMCP as _Server
    except ImportError as e:  # pragma: no cover
        raise SystemExit("The MCP server needs the 'mcp' package: pip install 'oalp[mcp]'") from e

mcp = _Server("oalp")


def _repo() -> Repository:
    root = os.environ.get("OALP_ROOT", ".")
    repo = Repository(root)
    if not repo.dir.exists():
        Repository.init(root)
    return repo


@mcp.tool()
def oalp_commit(agent_id: str, intent: str, reasoning: str | None = None,
                action: dict | None = None, outcome: dict | None = None,
                context: list | None = None, alternatives: list | None = None,
                branch: str | None = None) -> str:
    """Record an agent decision: what it intended, why, what it did and what happened.
    Returns the decision id (a SHA-256 content hash chained to the previous decision)."""
    return _repo().commit(agent=agent_id, intent=intent, reasoning=reasoning, action=action,
                          outcome=outcome, context=context, alternatives=alternatives, branch=branch)


@mcp.tool()
def oalp_log(ref: str | None = None, limit: int = 20) -> list[dict]:
    """Return decision history, newest first, for a branch or decision id."""
    return list(_repo().log(ref, limit))


@mcp.tool()
def oalp_show(ref: str) -> dict:
    """Return one decision record in full."""
    return _repo().read(ref)


@mcp.tool()
def oalp_branch(name: str, start: str | None = None) -> str:
    """Create a branch (e.g. one per agent run or task) starting from a decision."""
    return _repo().create_branch(name, start)


@mcp.tool()
def oalp_verify(ref: str | None = None) -> dict:
    """Check the log's integrity. Any edit to a past decision is reported."""
    issues = _repo().verify(ref)
    return {"ok": not issues, "issues": [str(i) for i in issues]}


def main() -> None:
    try:
        mcp.run()
    except OALPError as e:  # pragma: no cover
        raise SystemExit(f"oalp: {e}")


if __name__ == "__main__":
    main()
