"""GlintMesh: Gemini-backed interface generation with MCP tools and user datasets."""

import asyncio
import csv
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types
from pydantic import BaseModel, Field, field_validator

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_API_KEYS = [k.strip() for k in os.getenv("GEMINI_API_KEYS", GEMINI_API_KEY).split(",") if k.strip()]
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip() or "gemini-3.6-flash"
GEMINI_MODELS = [m.strip() for m in os.getenv("GEMINI_MODELS", GEMINI_MODEL).split(",") if m.strip()] or [GEMINI_MODEL]
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


class ImageAttachment(BaseModel):
    mime: str = Field(pattern=r"^image/(png|jpeg|webp|gif)$")
    data: str = Field(min_length=100, max_length=2000000)


class GenerateRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    lang: str = Field(default="es", pattern="^(es|en)$")
    context: str | None = Field(default=None, max_length=2000)
    dataset_id: str | None = Field(default=None, max_length=60)
    style_prompt: str | None = Field(default=None, max_length=1000)
    model: str | None = Field(default=None, max_length=80)
    temperature: float | None = Field(default=None, ge=0.0, le=1.0)
    mode: str = Field(default="full", pattern="^(full|data)$")
    images: list[ImageAttachment] = Field(default_factory=list, max_length=3)

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

    @field_validator("style_prompt", mode="before")
    @classmethod
    def trim_style(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @field_validator("model", mode="before")
    @classmethod
    def check_model(cls, value):
        if value is None:
            return None
        if isinstance(value, str) and value.strip() in GEMINI_MODELS:
            return value.strip()
        raise ValueError("Unknown model")


def event(kind: str, **payload) -> str:
    return f"data: {json.dumps({'type': kind, **payload}, ensure_ascii=False)}\n\n"


def _tool_schema(tool):
    """MCP v1 uses inputSchema, v2 uses input_schema."""
    return getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {}


def _result_is_error(result) -> bool:
    return bool(getattr(result, "isError", getattr(result, "is_error", False)))


UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
SHARE_DIR = BASE_DIR / "shares"
SHARE_DIR.mkdir(exist_ok=True)
DATASET_EXTS = {".csv", ".json"}
DATASET_MAX_BYTES = 2 * 1024 * 1024
DATASET_MAX_ROWS = 200


def _safe_dataset_id(filename: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", Path(filename).stem).strip("_")[:40] or "dataset"
    return f"{uuid.uuid4().hex[:8]}_{stem}"


def _dataset_path(dataset_id: str) -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", dataset_id or ""):
        raise HTTPException(status_code=404, detail="Dataset not found.")
    for ext in DATASET_EXTS:
        candidate = UPLOAD_DIR / f"{dataset_id}{ext}"
        if candidate.exists():
            return candidate
    raise HTTPException(status_code=404, detail="Dataset not found.")


def _parse_dataset_rows(path: Path) -> tuple[list[str], list[dict]]:
    if path.suffix == ".csv":
        text = path.read_text(encoding="utf-8-sig")
        reader = csv.DictReader(text.splitlines())
        columns = [c for c in (reader.fieldnames or []) if c]
        rows = []
        for row in reader:
            if len(rows) >= DATASET_MAX_ROWS:
                break
            rows.append({c: (row.get(c) or "") for c in columns})
        return columns, rows
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload if isinstance(payload, list) else payload.get("data", payload.get("rows", []))
    if not isinstance(items, list):
        raise ValueError("JSON must be a list of objects.")
    columns: list[str] = []
    for item in items:
        if isinstance(item, dict):
            for key in item:
                if key not in columns:
                    columns.append(key)
    rows = [{c: item.get(c, "") if isinstance(item, dict) else "" for c in columns} for item in items[:DATASET_MAX_ROWS]]
    return columns, rows


def _dataset_summary(name: str, columns: list[str], rows: list[dict]) -> dict:
    numeric: dict[str, dict] = {}
    for col in columns:
        values = []
        for row in rows:
            try:
                values.append(float(str(row.get(col, "")).replace(",", "").replace("$", "")))
            except (ValueError, TypeError):
                continue
        if len(values) >= max(2, len(rows) // 2) and values:
            numeric[col] = {"min": round(min(values), 2), "max": round(max(values), 2),
                            "mean": round(sum(values) / len(values), 2)}
    return {"columns": columns, "n_rows": len(rows), "numeric": numeric,
            "sample": rows[:5]}


def load_dataset_context(dataset_id: str) -> str:
    path = _dataset_path(dataset_id)
    try:
        columns, rows = _parse_dataset_rows(path)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=422, detail="Dataset could not be parsed.") from exc
    if not columns or not rows:
        raise HTTPException(status_code=422, detail="Dataset is empty.")
    summary = _dataset_summary(path.name, columns, rows)
    lines = [f"User dataset '{path.name}' ({summary['n_rows']} rows, columns: {', '.join(columns)})."]
    if summary["numeric"]:
        stats = "; ".join(f"{c}: min {s['min']}, max {s['max']}, mean {s['mean']}" for c, s in summary["numeric"].items())
        lines.append(f"Numeric summary: {stats}.")
    lines.append(f"Sample rows: {json.dumps(summary['sample'], ensure_ascii=False)[:1500]}")
    lines.append("Build the interface using this user data (label it as user-provided).")
    return "\n".join(lines)


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


async def run_agent_stream(user_message: str, lang: str = "es", context: str | None = None,
                     dataset_text: str | None = None, style_prompt: str | None = None,
                     model_choice: str | None = None, temperature: float | None = None,
                     mode: str = "full", images: list | None = None,
                     notify_token: str | None = None) -> AsyncIterator[str]:
    async def _pub(kind: str, text: str) -> None:
        """Mirror progress to the user's other live sockets (cross-tab liveness)."""
        if notify_token:
            try:
                await live.notify_agent(notify_token, kind, text)
            except Exception:
                pass
    yield event("status", content="Connecting to Gemini...")
    await _pub("status", "Connecting to Gemini...")
    mcp_tools = []
    if MCP_ENABLED:
        try:
            mcp_tools = await mcp_client.list_tools()
        except Exception:
            yield event("error", content="MCP tools are unavailable. Check the MCP server or set MCP_ENABLED=false.")
            await _pub("error", "MCP tools are unavailable.")
            return

    first_parts: list = [types.Part(text=user_message)]
    n_images = 0
    for img in (images or [])[:3]:
        try:
            import base64 as _b64
            payload = img.get("data", "") if isinstance(img, dict) else img.data
            mime = img.get("mime", "image/png") if isinstance(img, dict) else img.mime
            raw = _b64.b64decode(payload)
            if not raw or len(raw) > 1500000:
                continue
            first_parts.append(types.Part.from_bytes(data=raw, mime_type=mime))
            n_images += 1
        except Exception:
            continue
    if n_images:
        first_parts[0] = types.Part(text=user_message + (
            f"\n[User attached {n_images} image(s). IMAGE RULES: accept ONLY financial charts, graphs, "
            "tables or dashboards. Analyze them visually FIRST and reference what you see. "
            "If an image is NOT a financial graphic (meme, animal, person, landscape, random photo), "
            "do NOT break and do NOT output any HTML block: reply in 1-2 sentences explaining you can "
            "only build interfaces from financial charts/graphics, and ask for a proper one.]"))
        yield event("status", content=f"Analyzing {n_images} image(s)...")
        await _pub("status", f"Analyzing {n_images} image(s)...")
    contents = [types.Content(role="user", parts=first_parts)]
    if context:
        contents.append(types.Content(role="user", parts=[types.Part(
            text="Previous turn summary for continuity (adapt the new interface to it when relevant): " + context[:1500]
        )]))
    if dataset_text:
        contents.append(types.Content(role="user", parts=[types.Part(text=dataset_text)]))
    lang_note = "Reply in Spanish." if lang == "es" else "Reply in English."
    system_instruction = SYSTEM_PROMPT + "\n" + lang_note
    if style_prompt:
        system_instruction += ("\nUser style preference for all generated interfaces "
                               "(takes precedence over the default visual style): " + style_prompt[:800])
    if mode == "data":
        system_instruction += ("\nData-only mode: call the needed MCP tools, then reply with a 1-2 sentence "
                               "summary only. Do NOT output any HTML block.")
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=build_gemini_tools(mcp_tools) or None,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0.7 if temperature is None else temperature,
    )
    allowed_tools = {tool.name for tool in mcp_tools}
    initial_contents = list(contents)
    preferred = [model_choice] if model_choice else []
    ordered_models = preferred + [m for m in GEMINI_MODELS if m != model_choice]
    combos = [(key, model) for key in (GEMINI_API_KEYS or [GEMINI_API_KEY]) for model in ordered_models]
    for combo_index, (api_key, model) in enumerate(combos):
        last_combo = combo_index == len(combos) - 1
        contents = list(initial_contents)
        has_text = False
        try:
            async with genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=120000)).aio as client:
                for _ in range(6):
                    model_parts = []
                    function_calls = []
                    finish_reason = None
                    async for chunk in await client.models.generate_content_stream(
                        model=model, contents=contents, config=config,
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
                        await _pub("error", "Gemini could not finish this response.")
                        return
                    if not function_calls:
                        if has_text:
                            yield event("done", content="Response complete")
                            await _pub("done", "Response complete")
                        else:
                            yield event("error", content="Gemini returned no text. Try a different request.")
                            await _pub("error", "Gemini returned no text.")
                        return

                    contents.append(types.Content(role="model", parts=model_parts))
                    results = []
                    for call in function_calls:
                        call_args = dict(call.args or {})
                        yield event("tool_call", content=f"Fetching {call.name.replace('_', ' ')}...",
                                    tool=call.name, args=call_args)
                        await _pub("tool", f"Fetching {call.name.replace('_', ' ')}...")
                        try:
                            if call.name not in allowed_tools:
                                raise ValueError("Unknown tool")
                            data = await mcp_client.call_tool(call.name, call_args)
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
                    await _pub("status", "Generating interface from tool results...")
                yield event("error", content="Tool call limit reached. Please try a simpler request.")
                await _pub("error", "Tool call limit reached.")
        except Exception as error:
            # Do not expose SDK exception strings: they may contain request details or credentials.
            if getattr(error, "code", None) in (429, 404, 500, 502, 503, 504) and not last_combo:
                yield event("status", content="Usage limit reached, trying another model...")
                await _pub("status", "Usage limit reached, trying another model...")
                continue
            yield event("error", content=gemini_error_message(error))
            await _pub("error", gemini_error_message(error))


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return HTMLResponse((BASE_DIR / "static" / "index.html").read_text(encoding="utf-8"))


@app.post("/api/generate")
async def generate_interface(body: GenerateRequest, request: Request):
    if not GEMINI_API_KEYS:
        raise HTTPException(status_code=503, detail="Set GEMINI_API_KEY in the server .env file before generating.")
    dataset_text = load_dataset_context(body.dataset_id) if body.dataset_id else None
    images = [img.model_dump() for img in (body.images or [])]
    auth = request.headers.get("authorization", "")
    notify_token = auth[7:] if auth.lower().startswith("bearer ") else ""
    return StreamingResponse(run_agent_stream(body.message, body.lang, body.context, dataset_text,
                                              body.style_prompt, body.model, body.temperature, body.mode,
                                              images, notify_token=notify_token or None),
                             media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


USERS_FILE = BASE_DIR / "users.json"


class AuthBody(BaseModel):
    user: str = Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=4, max_length=100)


def _load_users() -> dict:
    try:
        data = json.loads(USERS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_users(data: dict) -> None:
    USERS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _hash_password(password: str, salt: str) -> str:
    import hashlib
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


@app.post("/api/auth/register")
async def auth_register(body: AuthBody):
    users = _load_users()
    key = body.user.lower()
    if key in users:
        raise HTTPException(status_code=409, detail="User already exists.")
    salt = uuid.uuid4().hex
    users[key] = {"user": body.user, "salt": salt,
                  "hash": _hash_password(body.password, salt), "sessions": []}
    _save_users(users)
    return {"user": body.user}


@app.post("/api/auth/login")
async def auth_login(body: AuthBody):
    users = _load_users()
    key = body.user.lower()
    record = users.get(key)
    if not record or record.get("hash") != _hash_password(body.password, record.get("salt", "")):
        raise HTTPException(status_code=401, detail="Invalid credentials.")
    token = uuid.uuid4().hex + uuid.uuid4().hex
    record.setdefault("sessions", []).append(token)
    _save_users(users)
    return {"user": record["user"], "token": token, "avatar": record.get("avatar")}


class AvatarBody(BaseModel):
    avatar: str = Field(min_length=100, max_length=400000)

    @field_validator("avatar", mode="before")
    @classmethod
    def check_avatar(cls, value):
        if isinstance(value, str) and re.fullmatch(
                r"data:image/(png|jpeg|webp|gif);base64,[A-Za-z0-9+/=]+", value.strip()):
            return value.strip()
        raise ValueError("Invalid avatar")


def _auth_record(request: Request) -> dict | None:
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else ""
    if not token:
        return None
    for record in _load_users().values():
        if token in record.get("sessions", []):
            return record
    return None


@app.get("/api/auth/me")
async def auth_me(request: Request):
    record = _auth_record(request)
    if record:
        return {"user": record["user"], "avatar": record.get("avatar")}
    return {"user": None}


@app.put("/api/auth/avatar")
async def auth_avatar(body: AvatarBody, request: Request):
    users = _load_users()
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else ""
    for key, record in users.items():
        if token and token in record.get("sessions", []):
            record["avatar"] = body.avatar[:400000]
            _save_users(users)
            return {"user": record["user"], "avatar": record["avatar"]}
    raise HTTPException(status_code=401, detail="Not signed in.")


class PasswordBody(BaseModel):
    current: str = Field(min_length=4, max_length=100)
    new: str = Field(min_length=4, max_length=100)


@app.put("/api/auth/password")
async def auth_password(body: PasswordBody, request: Request):
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else ""
    users = _load_users()
    for record in users.values():
        if token and token in record.get("sessions", []):
            if record.get("hash") != _hash_password(body.current, record.get("salt", "")):
                raise HTTPException(status_code=401, detail="Current password is incorrect.")
            salt = uuid.uuid4().hex
            record["salt"] = salt
            record["hash"] = _hash_password(body.new, salt)
            _save_users(users)
            return {"ok": True, "user": record["user"]}
    raise HTTPException(status_code=401, detail="Not signed in.")


@app.post("/api/auth/logout")
async def auth_logout(body: dict):
    token = str(body.get("token", ""))
    users = _load_users()
    for record in users.values():
        sessions = record.get("sessions", [])
        if token in sessions:
            sessions.remove(token)
    _save_users(users)
    return {"ok": True}


# ─── Live channel: WS ticks, threshold alerts, agent progress, prefs sync ─────
LIVE_TICK_SECONDS = 15
LIVE_MAX_SYMBOLS = 20
LIVE_MAX_WATCHES = 20


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_by_token(token: str) -> tuple[str | None, dict | None]:
    if not token:
        return None, None
    for key, record in _load_users().items():
        if token in record.get("sessions", []):
            return key, record
    return None, None


def _clean_symbol(value) -> str | None:
    if not isinstance(value, str):
        return None
    sym = re.sub(r"[^A-Za-z0-9.\-=]", "", value.strip().upper())[:12]
    return sym or None


def _clean_number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0 or number != number or number == float("inf"):
        return None
    return number


class LiveManager:
    """Tracks /ws/live connections; pushes ticks, alerts, agent progress, prefs."""

    def __init__(self):
        self.conns: dict[str, dict] = {}
        self._ticker_task = None
        self.last_agent: dict[str, dict] = {}

    async def connect(self, ws: WebSocket, token: str) -> str:
        await ws.accept()
        key, _ = _record_by_token(token or "")
        conn_id = uuid.uuid4().hex[:12]
        self.conns[conn_id] = {
            "ws": ws, "token": token or "", "user": ("user:" + key) if key else None,
            "symbols": set(), "watches": {}, "last": {},
        }
        self._ensure_ticker()
        hello: dict = {"type": "hello", "conn": conn_id, "live": MCP_ENABLED,
                       "models": GEMINI_MODELS, "tick_seconds": LIVE_TICK_SECONDS}
        if token and token in self.last_agent:
            hello["agent"] = self.last_agent[token]
        await self._send(conn_id, hello)
        return conn_id

    async def disconnect(self, conn_id: str) -> None:
        self.conns.pop(conn_id, None)

    async def _send(self, conn_id: str, msg: dict) -> None:
        conn = self.conns.get(conn_id)
        if not conn:
            return
        try:
            await conn["ws"].send_json(msg)
        except Exception:
            pass

    async def handle(self, conn_id: str, msg) -> None:
        conn = self.conns.get(conn_id)
        if not conn or not isinstance(msg, dict):
            return
        op = msg.get("op")
        if op == "ping":
            await self._send(conn_id, {"type": "pong", "ts": _utcnow()})
        elif op == "subscribe":
            symbols = []
            for raw in (msg.get("symbols") or [])[:LIVE_MAX_SYMBOLS]:
                sym = _clean_symbol(raw)
                if sym and sym not in symbols:
                    symbols.append(sym)
            watches = {}
            raw_watches = msg.get("watches") or {}
            if isinstance(raw_watches, dict):
                for raw_sym, cond in list(raw_watches.items())[:LIVE_MAX_WATCHES]:
                    sym = _clean_symbol(raw_sym)
                    if not sym or not isinstance(cond, dict):
                        continue
                    above = _clean_number(cond.get("above"))
                    below = _clean_number(cond.get("below"))
                    if above is None and below is None:
                        continue
                    watches[sym] = {"above": above, "below": below}
                    if sym not in symbols and len(symbols) < LIVE_MAX_SYMBOLS:
                        symbols.append(sym)
            conn["symbols"] = set(symbols)
            conn["watches"] = watches
            await self._send(conn_id, {"type": "subscribed", "symbols": sorted(symbols)})
        elif op == "unsubscribe":
            conn["symbols"] = set()
            conn["watches"] = {}
            await self._send(conn_id, {"type": "subscribed", "symbols": []})

    async def notify_agent(self, token: str, kind: str, text: str) -> None:
        if not token:
            return
        self.last_agent[token] = {"kind": kind, "text": text, "ts": _utcnow()}
        if len(self.last_agent) > 500:
            self.last_agent.pop(next(iter(self.last_agent)))
        for cid, conn in list(self.conns.items()):
            if conn["token"] == token:
                await self._send(cid, {"type": "agent", "kind": kind, "text": text})

    async def notify_sync(self, user_key: str | None, prefs: dict, exclude: str | None = None) -> None:
        if not user_key:
            return
        for cid, conn in list(self.conns.items()):
            if conn["user"] == user_key and cid != exclude:
                await self._send(cid, {"type": "sync", "prefs": prefs})

    async def _resolve_quote_tool(self) -> str | None:
        try:
            tools = await mcp_client.list_tools()
        except Exception:
            return None
        names = {tool.name for tool in tools}
        if "get_live_quote" in names:
            return "get_live_quote"
        if "get_stock_quote" in names:
            return "get_stock_quote"
        return None

    async def poll_once(self) -> None:
        symbols: set[str] = set()
        for conn in self.conns.values():
            symbols |= conn["symbols"]
        if not symbols or not MCP_ENABLED:
            return
        tool = await self._resolve_quote_tool()
        if not tool:
            for cid in list(self.conns):
                await self._send(cid, {"type": "status", "code": "no_quote_tool"})
            return
        for sym in sorted(symbols):
            try:
                data = await mcp_client.call_tool(tool, {"symbol": sym})
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            price = _clean_number(data.get("price"))
            if price is None:
                continue
            try:
                change = float(data.get("change_percent") or 0)
            except (TypeError, ValueError):
                change = 0
            tick = {"type": "tick", "symbol": sym, "price": price,
                    "change_percent": change, "ts": _utcnow()}
            for cid, conn in list(self.conns.items()):
                if sym not in conn["symbols"]:
                    continue
                await self._send(cid, tick)
                watch = conn["watches"].get(sym, {})
                prev = conn["last"].get(sym)
                above = watch.get("above")
                below = watch.get("below")
                if prev is not None:
                    if above is not None and prev < above <= price:
                        await self._send(cid, {"type": "alert", "symbol": sym, "price": price,
                                               "condition": "above", "threshold": above, "ts": tick["ts"]})
                    elif below is not None and prev > below >= price:
                        await self._send(cid, {"type": "alert", "symbol": sym, "price": price,
                                               "condition": "below", "threshold": below, "ts": tick["ts"]})
                conn["last"][sym] = price

    def _ensure_ticker(self) -> None:
        if self._ticker_task is None or self._ticker_task.done():
            self._ticker_task = asyncio.create_task(self._ticker_loop())

    async def _ticker_loop(self) -> None:
        while self.conns:
            try:
                await self.poll_once()
            except Exception:
                pass
            await asyncio.sleep(LIVE_TICK_SECONDS)


live = LiveManager()


@app.websocket("/ws/live")
async def ws_live(ws: WebSocket):
    token = ws.query_params.get("token", "")
    conn_id = await live.connect(ws, token)
    try:
        while True:
            await live.handle(conn_id, await ws.receive_json())
    except WebSocketDisconnect:
        await live.disconnect(conn_id)
    except Exception:
        await live.disconnect(conn_id)


class WatchBody(BaseModel):
    symbol: str = Field(min_length=1, max_length=12, pattern=r"^[A-Za-z0-9.\-=]{1,12}$")
    above: float | None = Field(default=None, gt=0)
    below: float | None = Field(default=None, gt=0)


class PrefsBody(BaseModel):
    model: str | None = Field(default=None, max_length=80)
    dataset_id: str | None = Field(default=None, max_length=60)
    lang: str | None = Field(default=None, pattern="^(es|en)$")
    watches: list[WatchBody] | None = Field(default=None, max_length=20)
    via: str | None = Field(default=None, max_length=20)


def _default_prefs() -> dict:
    return {"model": "", "dataset_id": None, "lang": "es", "watches": []}


def _sanitize_prefs(raw) -> dict:
    prefs = _default_prefs()
    if not isinstance(raw, dict):
        return prefs
    if isinstance(raw.get("model"), str) and raw["model"] in GEMINI_MODELS:
        prefs["model"] = raw["model"]
    if isinstance(raw.get("dataset_id"), str) and re.fullmatch(r"[a-zA-Z0-9_-]{1,60}", raw["dataset_id"]):
        prefs["dataset_id"] = raw["dataset_id"]
    if raw.get("lang") in ("es", "en"):
        prefs["lang"] = raw["lang"]
    watches = []
    if isinstance(raw.get("watches"), list):
        for item in raw["watches"][:LIVE_MAX_WATCHES]:
            if not isinstance(item, dict):
                continue
            sym = _clean_symbol(item.get("symbol"))
            above = _clean_number(item.get("above"))
            below = _clean_number(item.get("below"))
            if sym and (above is not None or below is not None):
                watches.append({"symbol": sym, "above": above, "below": below})
    prefs["watches"] = watches
    return prefs


@app.get("/api/prefs")
async def get_prefs(request: Request):
    if not _auth_record(request):
        raise HTTPException(status_code=401, detail="Not signed in.")
    _, record = _record_by_token(request.headers.get("authorization", "")[7:])
    return _sanitize_prefs((record or {}).get("prefs"))


@app.put("/api/prefs")
async def put_prefs(body: PrefsBody, request: Request):
    auth = request.headers.get("authorization", "")
    token = auth[7:] if auth.lower().startswith("bearer ") else ""
    users = _load_users()
    owner_key, record = None, None
    for key, candidate in users.items():
        if token and token in candidate.get("sessions", []):
            owner_key, record = key, candidate
            break
    if record is None:
        raise HTTPException(status_code=401, detail="Not signed in.")
    if body.model is not None and body.model != "" and body.model not in GEMINI_MODELS:
        raise HTTPException(status_code=422, detail="Unknown model.")
    prefs = _sanitize_prefs(record.get("prefs"))
    data = body.model_dump(exclude_unset=True)
    if "model" in data:
        prefs["model"] = data["model"] if data["model"] in GEMINI_MODELS else ""
    if "dataset_id" in data:
        dataset = data["dataset_id"]
        prefs["dataset_id"] = dataset if isinstance(dataset, str) and re.fullmatch(
            r"[a-zA-Z0-9_-]{1,60}", dataset) else None
    if "lang" in data and data["lang"] in ("es", "en"):
        prefs["lang"] = data["lang"]
    if "watches" in data:
        prefs["watches"] = _sanitize_prefs({"watches": [
            item.model_dump() for item in (body.watches or [])]})["watches"]
    record["prefs"] = prefs
    _save_users(users)
    await live.notify_sync("user:" + owner_key, prefs, exclude=data.get("via"))
    return prefs


@app.get("/api/datasets")
async def list_datasets():
    items = []
    for path in sorted(UPLOAD_DIR.glob("*")):
        if path.suffix not in DATASET_EXTS or not path.is_file():
            continue
        try:
            columns, rows = _parse_dataset_rows(path)
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        items.append({"id": path.stem, "name": path.name, "columns": columns, "n_rows": len(rows),
                      "size": path.stat().st_size, "sample": rows[:3]})
    return {"datasets": items}


class ToolCallRequest(BaseModel):
    tool: str = Field(min_length=1, max_length=80)
    args: dict = Field(default_factory=dict)


class ShareRequest(BaseModel):
    html: str = Field(min_length=100, max_length=500000)


@app.post("/api/tool-call")
async def direct_tool_call(body: ToolCallRequest):
    """Re-run a single MCP tool without Gemini (free live refresh for A2UI surfaces)."""
    if not MCP_ENABLED:
        raise HTTPException(status_code=503, detail="MCP tools are unavailable.")
    try:
        tools = await mcp_client.list_tools()
    except Exception:
        raise HTTPException(status_code=503, detail="MCP tools are unavailable.")
    if body.tool not in {tool.name for tool in tools}:
        raise HTTPException(status_code=404, detail="Unknown tool.")
    try:
        data = await mcp_client.call_tool(body.tool, dict(body.args or {}))
    except Exception:
        raise HTTPException(status_code=502, detail="The MCP tool could not complete the request.")
    return {"tool": body.tool, "data": data}


@app.post("/api/share")
async def share_interface(body: ShareRequest):
    """Save a generated interface and return a shareable link."""
    share_id = uuid.uuid4().hex[:12]
    (SHARE_DIR / f"{share_id}.html").write_text(body.html, encoding="utf-8")
    return {"id": share_id, "url": f"/share/{share_id}"}


@app.get("/share/{share_id}", response_class=HTMLResponse)
async def serve_share(share_id: str):
    if not re.fullmatch(r"[a-f0-9]{12}", share_id or ""):
        raise HTTPException(status_code=404, detail="Not found.")
    path = SHARE_DIR / f"{share_id}.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found.")
    return HTMLResponse(path.read_text(encoding="utf-8"))


@app.delete("/api/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str):
    path = _dataset_path(dataset_id)
    path.unlink(missing_ok=True)
    return {"deleted": dataset_id}


@app.post("/api/datasets")
async def upload_dataset(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in DATASET_EXTS:
        raise HTTPException(status_code=415, detail="Only .csv and .json files are accepted.")
    raw = await file.read()
    if not raw or len(raw) > DATASET_MAX_BYTES:
        raise HTTPException(status_code=413, detail="File must be non-empty and under 2 MB.")
    dataset_id = _safe_dataset_id(file.filename or "dataset")
    path = UPLOAD_DIR / f"{dataset_id}{ext}"
    path.write_bytes(raw)
    try:
        columns, rows = _parse_dataset_rows(path)
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Dataset could not be parsed.")
    if not columns or not rows:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="Dataset is empty.")
    return {"id": dataset_id, "name": path.name, "columns": columns, "n_rows": len(rows),
            "size": len(raw), "sample": rows[:5]}


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
            "gemini_configured": bool(GEMINI_API_KEYS), "model": GEMINI_MODEL, "models": GEMINI_MODELS,
            "mcp_enabled": MCP_ENABLED, "ws_live": True, "tick_seconds": LIVE_TICK_SECONDS,
            "mcp_server": "finflow-financial-tools", "protocol": "A2UI over MCP"}


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)