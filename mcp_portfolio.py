"""
GlintMesh user portfolios MCP server (writable: save/list/get/delete).
Holdings are the user's own data; live valuation happens via market tools.
Compatible with MCP Python SDK v1 (FastMCP) and v2 (MCPServer).
"""

import json
import re
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP
    server = FastMCP("glintmesh-user-portfolios")
except ModuleNotFoundError:
    from mcp.server.mcpserver import MCPServer
    server = MCPServer("glintmesh-user-portfolios")

STORE = Path(__file__).resolve().parent / "portfolios"
STORE.mkdir(exist_ok=True)


def _check_name(name: str) -> str:
    clean = (name or "").strip()[:40]
    if not re.fullmatch(r"[A-Za-z0-9 _-]+", clean):
        raise RuntimeError("Use letters, numbers, spaces, - or _ for the name.")
    return clean


def _path(name: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]+", "_", _check_name(name)).strip("_") or "portfolio"
    return STORE / f"{safe}.json"


@server.tool()
def save_portfolio(name: str, holdings: list[str]) -> str:
    """Save the user's own portfolio holdings (up to 20 ticker symbols)."""
    symbols = []
    for raw in holdings or []:
        sym = str(raw).strip().upper()[:12]
        if sym and sym not in symbols:
            symbols.append(sym)
    if not symbols:
        raise RuntimeError("Provide at least one ticker symbol.")
    data = {"name": _check_name(name), "holdings": symbols[:20]}
    _path(name).write_text(json.dumps(data), encoding="utf-8")
    return json.dumps({**data, "source": "user"})


@server.tool()
def list_portfolios() -> str:
    """List the user's saved portfolios."""
    out = []
    for path in sorted(STORE.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            out.append({"name": data.get("name", path.stem), "holdings": data.get("holdings", [])})
        except (ValueError, OSError):
            continue
    return json.dumps(out)


@server.tool()
def get_portfolio(name: str) -> str:
    """Get one of the user's saved portfolios with its holdings."""
    path = _path(name)
    if not path.exists():
        raise RuntimeError(f"Portfolio '{name}' not found.")
    data = json.loads(path.read_text(encoding="utf-8"))
    return json.dumps({**data, "source": "user"})


@server.tool()
def delete_portfolio(name: str) -> str:
    """Delete one of the user's saved portfolios."""
    path = _path(name)
    if not path.exists():
        raise RuntimeError(f"Portfolio '{name}' not found.")
    path.unlink()
    return json.dumps({"deleted": _check_name(name)})


if __name__ == "__main__":
    server.run(transport="stdio")
