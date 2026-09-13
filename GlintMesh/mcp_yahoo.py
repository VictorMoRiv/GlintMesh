"""
GlintMesh live market data MCP server (real data via Yahoo Finance, no API key).
JSON schemas intentionally match mcp_server.py demo tools, plus "source": "live",
so the A2UI native renderer works unchanged.
Compatible with MCP Python SDK v1 (FastMCP) and v2 (MCPServer).
"""

import json
import urllib.request
from datetime import datetime, timezone

try:
    from mcp.server.fastmcp import FastMCP
    server = FastMCP("glintmesh-live-market")
except ModuleNotFoundError:
    from mcp.server.mcpserver import MCPServer
    server = MCPServer("glintmesh-live-market")

_UA = {"User-Agent": "Mozilla/5.0 (GlintMesh demo)"}
_TIMEOUT = 15


def _chart(symbol: str, range_: str, interval: str = "1d") -> dict:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval={interval}&range={range_}"
    req = urllib.request.Request(url, headers=_UA)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            payload = json.load(resp)
    except Exception as exc:
        raise RuntimeError(f"quote unavailable for {symbol}") from exc
    try:
        result = payload["chart"]["result"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"quote unavailable for {symbol}") from exc
    if result.get("meta", {}).get("instrumentType") == "ERROR" or not result.get("timestamp"):
        raise RuntimeError(f"quote unavailable for {symbol}")
    return result


def _price(result: dict) -> float:
    meta = result["meta"]
    price = meta.get("regularMarketPrice")
    if price is None:
        closes = (result.get("indicators", {}).get("quote") or [{}])[0].get("close") or []
        closes = [c for c in closes if c is not None]
        price = closes[-1] if closes else 0.0
    return float(price)


@server.tool()
def get_live_quote(symbol: str) -> str:
    """Get a LIVE market quote for a ticker (price, change, volume, 52w range)."""
    result = _chart(symbol.upper(), "2d")
    meta = result["meta"]
    price = _price(result)
    prev = float(meta.get("chartPreviousClose") or meta.get("previousClose") or price)
    change = price - prev
    result_out = {
        "symbol": symbol.upper(),
        "price": round(price, 2),
        "change": round(change, 2),
        "change_percent": round((change / prev * 100) if prev else 0.0, 2),
        "volume": int(meta.get("regularMarketVolume") or 0),
        "market_cap": meta.get("marketCap"),
        "high_52w": meta.get("fiftyTwoWeekHigh"),
        "low_52w": meta.get("fiftyTwoWeekLow"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "live",
    }
    return json.dumps(result_out)


@server.tool()
def get_live_history(symbol: str, days: int = 30) -> str:
    """Get LIVE historical OHLCV daily data for a ticker (up to ~1 year)."""
    days = max(1, min(int(days), 365))
    range_ = "5d" if days <= 5 else ("1mo" if days <= 30 else ("3mo" if days <= 90 else ("6mo" if days <= 180 else "1y")))
    result = _chart(symbol.upper(), range_)
    stamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    rows = []
    for i, ts in enumerate(stamps):
        try:
            close = quote.get("close", [])[i]
            if close is None:
                continue
            rows.append({
                "date": datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d"),
                "open": round(quote.get("open", [])[i] or close, 2),
                "high": round(quote.get("high", [])[i] or close, 2),
                "low": round(quote.get("low", [])[i] or close, 2),
                "close": round(close, 2),
                "volume": int((quote.get("volume", [])[i] or 0)),
            })
        except IndexError:
            continue
    rows = rows[-days:]
    if not rows:
        raise RuntimeError(f"history unavailable for {symbol}")
    out = {
        "symbol": symbol.upper(),
        "period_days": len(rows),
        "data": rows,
        "start_price": rows[0]["close"],
        "end_price": rows[-1]["close"],
        "total_return": round((rows[-1]["close"] / rows[0]["close"] - 1) * 100, 2),
        "source": "live",
    }
    return json.dumps(out)


_INDEX_MAP = {
    "SP500": "^GSPC",
    "NASDAQ": "^IXIC",
    "DOW": "^DJI",
    "IPC": "^MXX",
    "FTSE": "^FTSE",
}
_INDEX_NAMES = {"SP500": "S&P 500", "NASDAQ": "NASDAQ", "DOW": "Dow Jones", "IPC": "IPC Mexico", "FTSE": "FTSE 100"}


@server.tool()
def get_live_indices() -> str:
    """Get LIVE values for S&P 500, NASDAQ, Dow Jones, IPC Mexico and FTSE 100."""
    out = {}
    for key, ticker in _INDEX_MAP.items():
        try:
            result = _chart(ticker, "2d")
            price = _price(result)
            prev = float(result["meta"].get("chartPreviousClose") or result["meta"].get("previousClose") or price)
            change = price - prev
            out[key] = {
                "name": _INDEX_NAMES[key],
                "value": round(price, 2),
                "change": round(change, 2),
                "change_percent": round((change / prev * 100) if prev else 0.0, 2),
            }
        except RuntimeError:
            continue
    if not out:
        raise RuntimeError("indices unavailable")
    out["source"] = "live"
    return json.dumps(out)


_FX_CURRENCIES = ["EUR", "GBP", "JPY", "MXN", "CAD", "AUD", "CHF", "CNY", "BRL"]


@server.tool()
def get_live_fx(base_currency: str = "USD") -> str:
    """Get LIVE foreign exchange rates relative to a base currency."""
    base = base_currency.upper()
    usd_rates = {}
    for cur in _FX_CURRENCIES:
        try:
            result = _chart(f"USD{cur}=X", "1d")
            usd_rates[cur] = _price(result)
        except RuntimeError:
            continue
    if not usd_rates:
        raise RuntimeError("fx rates unavailable")
    if base == "USD":
        rates = {k: round(v, 4) for k, v in usd_rates.items()}
    else:
        base_in_usd = usd_rates.get(base)
        if base_in_usd is None:
            try:
                base_in_usd = _price(_chart(f"USD{base}=X", "1d"))
            except RuntimeError:
                raise RuntimeError(f"fx base {base} unavailable")
        rates = {k: round(v / base_in_usd, 4) for k, v in usd_rates.items() if k != base}
        rates["USD"] = round(1 / base_in_usd, 4)
    out = {
        "base": base,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "rates": rates,
        "source": "live",
    }
    return json.dumps(out)


if __name__ == "__main__":
    server.run(transport="stdio")
