"""
GlintMesh ECB reference rates MCP server (real official data, no API key).
Compatible with MCP Python SDK v1 (FastMCP) and v2 (MCPServer).
"""

import json
import xml.etree.ElementTree as ET

import httpx

try:
    from mcp.server.fastmcp import FastMCP
    server = FastMCP("glintmesh-ecb-rates")
except ModuleNotFoundError:
    from mcp.server.mcpserver import MCPServer
    server = MCPServer("glintmesh-ecb-rates")

_ECB_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"


@server.tool()
def get_ecb_rates() -> str:
    """Get LIVE official ECB euro foreign exchange reference rates."""
    try:
        resp = httpx.get(_ECB_URL, timeout=15, headers={"User-Agent": "Mozilla/5.0 (GlintMesh demo)"})
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except Exception as exc:
        raise RuntimeError("ECB rates unavailable") from exc
    ns = {"e": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
    day = root.find("e:Cube/e:Cube[@time]", ns)
    if day is None:
        raise RuntimeError("ECB rates unavailable")
    rates = {}
    for cube in day.findall("e:Cube[@currency]", ns):
        try:
            rates[cube.get("currency")] = round(float(cube.get("rate")), 4)
        except (TypeError, ValueError):
            continue
    if not rates:
        raise RuntimeError("ECB rates unavailable")
    return json.dumps({
        "base": "EUR",
        "date": day.get("time"),
        "rates": rates,
        "source": "live-ecb",
    })


if __name__ == "__main__":
    server.run(transport="stdio")
