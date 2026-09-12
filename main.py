"""FinFlow AI: Gemini-backed interface generation with optional MCP tools."""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, field_validator

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip() or "gemini-3.6-flash"
MCP_ENABLED = os.getenv("MCP_ENABLED", "false").lower() in {"true", "1", "yes"}

app = FastAPI(title="GlintMesh", version="2.0.0")

SYSTEM_PROMPT = """You are GlintMesh, an assistant that builds financial web interfaces over MCP with A2UI surfaces.
Respond in the user's language (Spanish 'es' or English 'en' as instructed in the user message prefix).
For greetings or general questions, reply briefly in plain text in that language.
For an interface request, briefly explain what you are building, then return a complete HTML
 document in a fenced ```html block. Include inline CSS and JavaScript. Use Bootstrap 5 via CDN,
Chart.js when useful. Default visual style: minimalist enterprise. Clean layouts with generous
whitespace, a restrained palette (slate grays plus one emerald/blue accent), simple cards with
subtle borders, professional typography, and clear data tables. Avoid heavy glassmorphism,
gradients, or playful decoration unless the user explicitly asks for a different style.
If the user requests another look (dark neon, colorful, playful), follow their request instead.
Do not use emojis. Make the interface responsive and format financial numbers clearly.
Never describe invented or simulated numbers as live data. When no data source is available,
use clearly labeled sample data or the user's supplied values. Demo MCP tools return
simulated demonstration data: label it as such. Tools named get_live_* return real
market data via Yahoo Finance: present it as live. Do not invent a successful tool result.
When MCP tools are used, structure the visible output as A2UI-style surfaces (cards, charts, tables).
"""


class GenerateRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    lang: str = Field(default="es", pattern="^(es|en)$")
    context: str | None = Field(default=None, max_length=2000)

    @field_validator("message", mode="before")
    @classmethod
    def trim_message(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("context", mode="before")
    @classmethod
    def trim_context(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


def event(kind: str, **payload) -> str:
    return f"data: {json.dumps({'type': kind, **payload}, ensure_ascii=False)}\n\n"


def _tool_schema(tool):
    """MCP v1 uses inputSchema, v2 uses input_schema."""
    return getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {}


def _result_is_error(result) -> bool:
    return bool(getattr(result, "isError", getattr(result, "is_error", False)))


def _load_mcp_servers():
    """Servers are configured in mcp_servers.json; falls back to the demo server."""
    try:
        cfg = json.loads((BASE_DIR / "mcp_servers.json").read_text(encoding="utf-8"))
        servers = [s for s in cfg.get("servers", []) if s.get("name") and s.get("script")]
        if servers:
            return servers
    except Exception:
        pass
    return [{"name": "demo", "script": "mcp_server.py", "label": "Demo (simulated data)"}]


MCP_SERVERS = _load_mcp_servers()


class MCPFinancialClient:
    """Multi-server MCP adapter; startup does not require an MCP connection."""

    def __init__(self, servers=None):
        self.servers = servers if servers is not None else MCP_SERVERS
        self._tools_cache = None
        self._by_server = {}
        self._owner = {}

    async def _request(self, server, tool_name=None, tool_args=None):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(command=sys.executable, args=[str(BASE_DIR / server["script"])])
        async with asyncio.timeout(30):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    if tool_name is None:
                        return (await session.list_tools()).tools
                    result = await session.call_tool(tool_name, tool_args or {})
                    if _result_is_error(result):
                        raise RuntimeError("MCP tool failed")
                    text = "\n".join(
                        getattr(part, "text", "")
                        for part in result.content
                        if getattr(part, "type", None) == "text"
                    )
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        return {"text": text}

    async def list_tools(self):
        if self._tools_cache is None:
            flat, by_server, owner = [], {}, {}
            for srv in self.servers:
                tools = await self._request(srv)
                by_server[srv["name"]] = tools
                for tool in tools:
                    if tool.name in owner:
                        continue
                    owner[tool.name] = srv
                    flat.append(tool)
            self._tools_cache = flat
            self._by_server = by_server
            self._owner = owner
        return self._tools_cache

    async def call_tool(self, name, arguments):
        if self._tools_cache is None:
            await self.list_tools()
        server = self._owner.get(name, self.servers[0] if self.servers else None)
        if server is None:
            raise RuntimeError("No MCP server configured")
        return await self._request(server, name, arguments)

    async def list_tools_by_server(self):
        await self.list_tools()
        return [{
            "name": srv["name"],
            "label": srv.get("label", srv["name"]),
            "tools": self._by_server.get(srv["name"], []),
        } for srv in self.servers]


mcp_client = MCPFinancialClient()


def build_gemini_tools(mcp_tools):
    declarations = [types.FunctionDeclaration(
        name=tool.name,
        description=tool.description or tool.name,
        parameters_json_schema=_tool_schema(tool),
    ) for tool in mcp_tools]
    return [types.Tool(function_declarations=declarations)] if declarations else []


def gemini_error_message(error):
    code = getattr(error, "code", None)
    if code in (401, 403):
        return "Gemini authentication failed. Check the server API key and its permissions."
    if code == 429:
        return "Gemini usage limit reached. Wait a moment and try again."
    if code == 404:
        return "The configured Gemini model is unavailable. Check GEMINI_MODEL on the server."
    if code in (500, 502, 503, 504):
        return "Gemini is temporarily unavailable. Please try again shortly."
    return "Could not complete the Gemini response. Check the server connection and try again."


async def run_agent_stream(user_message: str, lang: str = "es", context: str | None = None) -> AsyncIterator[str]:
    yield event("status", content="Connecting to Gemini...")
    mcp_tools = []
    if MCP_ENABLED:
        try:
            mcp_tools = await mcp_client.list_tools()
        except Exception:
            yield event("error", content="MCP tools are unavailable. Check the MCP server or set MCP_ENABLED=false.")
            return

    contents = [types.Content(role="user", parts=[types.Part(text=user_message)])]
    if context:
        contents.append(types.Content(role="user", parts=[types.Part(
            text="Previous turn summary for continuity (adapt the new interface to it when relevant): " + context[:1500]
        )]))
    lang_note = "Reply in Spanish." if lang == "es" else "Reply in English."
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT + "\n" + lang_note,
        tools=build_gemini_tools(mcp_tools) or None,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.7,
    )
    allowed_tools = {tool.name for tool in mcp_tools}
    has_text = False
    try:
        async with genai.Client(api_key=GEMINI_API_KEY, http_options=types.HttpOptions(timeout=120000)).aio as client:
            for _ in range(6):
                model_parts = []
                function_calls = []
                finish_reason = None
                async for chunk in await client.models.generate_content_stream(
                    model=GEMINI_MODEL, contents=contents, config=config,
                ):
                    candidates = chunk.candidates or []
                    if not candidates:
                        continue
                    candidate = candidates[0]
                    if candidate.finish_reason:
                        finish_reason = candidate.finish_reason
                    for part in (candidate.content.parts if candidate.content else []) or []:
                        # Preserve complete parts, including Gemini thought signatures, for tool follow-ups.
                        model_parts.append(part)
                        if part.function_call:
                            function_calls.append(part.function_call)
                        elif part.text and not part.thought:
                            has_text = True
                            yield event("text_chunk", content=part.text)

                if finish_reason and finish_reason != types.FinishReason.STOP:
                    yield event("error", content="Gemini could not finish this response. Try a shorter or different request.")
                    return
                if not function_calls:
                    if has_text:
                        yield event("done", content="Response complete")
                    else:
                        yield event("error", content="Gemini returned no text. Try a different request.")
                    return

                contents.append(types.Content(role="model", parts=model_parts))
                results = []
                for call in function_calls:
                    yield event("tool_call", content=f"Fetching {call.name.replace('_', ' ')}...")
                    try:
                        if call.name not in allowed_tools:
                            raise ValueError("Unknown tool")
                        data = await mcp_client.call_tool(call.name, dict(call.args or {}))
                        yield event("tool_result", tool=call.name, data=data)
                        result = {"result": data}
                    except Exception:
                        result = {"error": "The MCP tool could not complete the request."}
                        yield event("tool_result", tool=call.name, data=result, failed=True)
                    results.append(types.Part(function_response=types.FunctionResponse(
                        name=call.name, id=call.id, response=result,
                    )))
                contents.append(types.Content(role="user", parts=results))
                yield event("status", content="Generating interface from tool results...")
            yield event("error", content="Tool call limit reached. Please try a simpler request.")
    except Exception as error:
        # Do not expose SDK exception strings: they may contain request details or credentials.
        yield event("error", content=gemini_error_message(error))


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return HTMLResponse((BASE_DIR / "static" / "index.html").read_text(encoding="utf-8"))


@app.post("/api/generate")
async def generate_interface(body: GenerateRequest):
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="Set GEMINI_API_KEY in the server .env file before generating.")
    return StreamingResponse(run_agent_stream(body.message, body.lang, body.context), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


@app.get("/api/tools")
async def list_tools():
    if not MCP_ENABLED:
        return {"enabled": False, "tools": [], "servers": []}
    try:
        groups = await mcp_client.list_tools_by_server()
        return {"enabled": True, "tools": [
            {"name": tool.name, "description": tool.description,
             "parameters": _tool_schema(tool), "server": group["name"]}
            for group in groups for tool in group["tools"]
        ], "servers": [
            {"name": group["name"], "label": group["label"],
             "tools": [{"name": tool.name, "description": tool.description,
                        "parameters": _tool_schema(tool)} for tool in group["tools"]]}
            for group in groups
        ]}
    except Exception:
        raise HTTPException(status_code=503, detail="MCP tools are unavailable.")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "GlintMesh", "version": "2.0.0",
            "gemini_configured": bool(GEMINI_API_KEY), "model": GEMINI_MODEL, "mcp_enabled": MCP_ENABLED,
            "mcp_server": "finflow-financial-tools", "protocol": "A2UI over MCP"}


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)