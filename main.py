"""GlintMesh: Gemini-backed interface generation with MCP tools and user datasets."""

import asyncio
import csv
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import AsyncIterator

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
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
# Secundario compatible OpenAI. Groq es el secundario activo; DeepSeek queda como alias legacy.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip() or "openai/gpt-oss-120b"
GROQ_MODELS = [m.strip() for m in os.getenv("GROQ_MODELS", GROQ_MODEL).split(",") if m.strip()] or [GROQ_MODEL]
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip().rstrip("/") or "https://api.groq.com/openai/v1"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat"
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip().rstrip("/")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "auto").strip().lower() or "auto"
if LLM_PROVIDER not in {"gemini", "groq", "deepseek", "auto"}:
    LLM_PROVIDER = "auto"


def _is_secondary_model(name: str | None) -> bool:
    """True si el modelo pertenece al secundario (Groq / legacy DeepSeek), no a Gemini."""
    if not name or not isinstance(name, str):
        return False
    n = name.strip()
    if n in {GROQ_MODEL, DEEPSEEK_MODEL, "deepseek-chat", "deepseek-reasoner"} or n in GROQ_MODELS:
        return True
    if n.startswith(("llama-", "qwen-", "openai/", "moonshotai/", "mixtral-", "gemma-", "deepseek")):
        return True
    return False


def _secondary_llm_config(model_choice: str | None = None) -> dict:
    """Resuelve el proveedor secundario: Groq primero, DeepSeek como legacy.

    Devuelve dict con {label, api_key, model, base_url}.
    NOTA: un model_choice de Gemini se ignora aquí — cada proveedor usa sus
    propios modelos. Solo se respeta model_choice si es un modelo del secundario.
    """
    groq_key = GROQ_API_KEY
    legacy_key = DEEPSEEK_API_KEY
    api_key = groq_key or legacy_key
    label = "Groq" if groq_key else "DeepSeek"
    base_url = GROQ_BASE_URL if groq_key else (DEEPSEEK_BASE_URL or "https://api.deepseek.com")
    default_model = GROQ_MODEL if groq_key else DEEPSEEK_MODEL
    if _is_secondary_model(model_choice):
        model = model_choice.strip()
    else:
        model = default_model
    return {"label": label, "api_key": api_key, "model": model, "base_url": base_url}


def _secondary_configured() -> bool:
    return bool(GROQ_API_KEY or DEEPSEEK_API_KEY)
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
GROUNDING RULES (mandatory, highest priority):
- Every name, number, date, amount, score, or fact you present as real MUST come
  verbatim from an MCP tool result, the user's dataset, or the user's message.
- Never invent clients, companies, amounts, scores, dates, or transactions. Never
  fill in a missing field with a plausible value: if a requested field does not exist
  in the tool results, explicitly say that field is not available in the database.
- If a query returns zero documents, report "no records found" and STOP: do not
  fabricate a replacement table.
- Any example or placeholder value MUST be labeled "dato de ejemplo (no real)".
- Before emitting a table built from MongoDB, re-check each cell against the tool
  output you received; drop any row you cannot trace back to it.
- When the user asks for stored data without naming a collection, DISCOVER it:
  call mongo_list_collections (omit database to use the server default), then
  mongo_get_schema / mongo_find. Do not ask the user for collection names you
  can discover yourself with one tool call.
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
    provider: str | None = Field(default=None, pattern="^(gemini|groq|deepseek|auto)$")

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
        allowed = (
            set(GEMINI_MODELS)
            | set(GROQ_MODELS)
            | {GROQ_MODEL, DEEPSEEK_MODEL, "deepseek-chat", "deepseek-reasoner"}
            | {"llama-3.3-70b-versatile", "llama-3.1-8b-instant",
               "openai/gpt-oss-120b", "openai/gpt-oss-20b",
               "qwen/qwen3-32b", "moonshotai/kimi-k2-instruct-0905"}
        )
        if isinstance(value, str) and value.strip() in allowed:
            return value.strip()
        # Acepta prefijos típicos de Groq para no bloquear modelos nuevos.
        if isinstance(value, str) and value.strip().startswith(
            ("llama-", "qwen-", "openai/", "moonshotai/", "mixtral-", "gemma-", "deepseek")
        ):
            return value.strip()
        raise ValueError("Unknown model")


def sanitize_secret(text: str) -> str:
    if not isinstance(text, str) or not text:
        return ""
    all_keys = [GROQ_API_KEY, DEEPSEEK_API_KEY, GEMINI_API_KEY] + GEMINI_API_KEYS
    for k in all_keys:
        if k and len(k) >= 4:
            text = text.replace(k, "[REDACTED]")
    return text


def event(kind: str, **payload) -> str:
    clean = {}
    for k, v in payload.items():
        if isinstance(v, str):
            clean[k] = sanitize_secret(v)
        else:
            clean[k] = v
    return f"data: {json.dumps({'type': kind, **clean}, ensure_ascii=False)}\n\n"


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

        # The SDK filters inherited environment variables. Forward only the names
        # explicitly requested by each server; values never enter tool metadata.
        env = {name: os.environ[name] for name in server.get("env_vars", []) if name in os.environ}
        params = StdioServerParameters(
            command=sys.executable, args=[str(BASE_DIR / server["script"])], env=env,
        )
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


def _extract_status_code(error) -> int | None:
    code = getattr(error, "code", None) or getattr(error, "status_code", None)
    if isinstance(code, int):
        return code
    resp = getattr(error, "response", None)
    if resp is not None:
        sc = getattr(resp, "status_code", None)
        if isinstance(sc, int):
            return sc
    m = re.search(r"\b(401|403|404|429|500|502|503|504)\b", str(error))
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return None


def _looks_like_quota_error(error) -> bool:
    """Detecta errores de cuota/límite aunque el SDK no traiga código numérico.

    Solo se usa para decidir el fallback a Groq; el texto crudo nunca se reenvía.
    """
    try:
        text = str(error).lower()
    except Exception:
        text = ""
    try:
        text += " " + json.dumps(getattr(error, "details", None), default=str).lower()
    except Exception:
        pass
    keywords = (
        "quota", "rate limit", "rate_limit", "ratelimit", "resource_exhausted",
        "too many requests", "exhausted", "usage limit", "billing",
        "generate_content_free_tier", "free_tier",
    )
    return any(k in text for k in keywords)


def gemini_error_message(error, lang="en"):
    code = _extract_status_code(error)
    if code in (401, 403):
        if lang == "es":
            return "Autenticación fallida. Revisa la clave de API y sus permisos en el archivo .env."
        return "Gemini authentication failed. Check the server API key and its permissions."
    if code == 429:
        # Read structured quota identifiers, never forward raw SDK error text.
        payload = getattr(error, "details", None)
        if isinstance(payload, dict):
            payload = payload.get("error", payload)
        details = payload.get("details", []) if isinstance(payload, dict) else []
        daily = any(
            "PerDay" in str(violation.get("quotaId", ""))
            for detail in (details if isinstance(details, list) else []) if isinstance(detail, dict)
            for violation in (detail.get("violations") or []) if isinstance(violation, dict)
        )
        if daily:
            if lang == "es":
                return ("Se alcanzó la cuota diaria de Gemini para este proyecto y modelo. "
                        "Se restablece a medianoche, hora del Pacífico. Cambiar la clave del mismo "
                        "proyecto no renueva la cuota. Revisa tus límites y facturación en Google AI Studio.")
            return ("Gemini's daily quota for this project and model has been reached. "
                    "It resets at midnight Pacific time. Changing keys within the same project "
                    "does not renew the quota. Check your limits and billing in Google AI Studio.")
        if lang == "es":
            return "Cuota agotada o límite de uso alcanzado. Revisa las cuotas del proyecto en Google AI Studio."
        return "Gemini usage limit reached. Check the project's quotas in Google AI Studio."
    if code == 404:
        if lang == "es":
            return "Modelo no disponible. El modelo configurado de Gemini no está disponible. Revisa GEMINI_MODEL en el servidor."
        return "The configured Gemini model is unavailable. Check GEMINI_MODEL on the server."
    if code in (500, 502, 503, 504):
        if lang == "es":
            return "Error temporal del servicio. Gemini no está disponible temporalmente. Inténtalo de nuevo más tarde."
        return "Gemini is temporarily unavailable. Please try again shortly."
    if lang == "es":
        return "No se pudo completar la respuesta de Gemini. Revisa la conexión del servidor e inténtalo de nuevo."
    return "Could not complete the Gemini response. Check the server connection and try again."


def groq_error_message(error, lang="es", label="Groq"):
    code = _extract_status_code(error)
    if code in (401, 403):
        if lang == "es":
            return "Autenticación fallida. Revisa la clave de API y sus permisos en el archivo .env."
        return f"{label} authentication failed. Check GROQ_API_KEY and its permissions."
    if code == 429:
        if lang == "es":
            return "Cuota agotada o límite de uso alcanzado. Revisa tu saldo y facturación en Groq."
        return f"{label} quota exhausted or usage limit reached. Check your balance and billing."
    if code == 404:
        if lang == "es":
            return "Modelo no disponible. El modelo configurado no está disponible. Revisa GROQ_MODEL en el archivo .env."
        return f"The configured {label} model is unavailable. Check GROQ_MODEL on the server."
    if code in (500, 502, 503, 504):
        if lang == "es":
            return f"Error temporal del servicio. {label} no está disponible temporalmente. Inténtalo de nuevo más tarde."
        return f"{label} is temporarily unavailable. Please try again shortly."
    if isinstance(error, (httpx.TimeoutException, TimeoutError)):
        if lang == "es":
            return f"Error temporal del servicio. Tiempo de espera agotado al conectar con {label}."
        return f"{label} request timed out. Please try again."
    if isinstance(error, httpx.RequestError):
        if lang == "es":
            return f"Error temporal del servicio. No se pudo conectar con {label}."
        return f"Could not connect to {label}. Check network connection."
    if lang == "es":
        return f"No se pudo completar la respuesta de {label}. Inténtalo de nuevo."
    return f"Could not complete the {label} response. Check the connection and try again."


def deepseek_error_message(error, lang="es"):
    # Alias legacy: mantiene compatibilidad con el proveedor secundario anterior.
    cfg_label = "Groq" if GROQ_API_KEY else "DeepSeek"
    return groq_error_message(error, lang, label=cfg_label)


def missing_key_error_message(provider: str, lang: str = "es") -> str:
    if provider == "gemini":
        return (
            "Clave de API ausente. Configura GEMINI_API_KEY en el archivo .env."
            if lang == "es"
            else "Missing API key. Set GEMINI_API_KEY in the server .env file before generating."
        )
    if provider in ("groq", "deepseek"):
        return (
            "Clave de API ausente. Configura GROQ_API_KEY en el archivo .env."
            if lang == "es"
            else "Missing API key. Set GROQ_API_KEY in the server .env file before generating."
        )
    return (
        "Clave de API ausente. Configura GEMINI_API_KEY o GROQ_API_KEY en el archivo .env."
        if lang == "es"
        else "Missing API key. Set GEMINI_API_KEY or GROQ_API_KEY in the server .env file before generating."
    )


class DeepSeekAPIError(Exception):
    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        self.code = status_code
        super().__init__(message)


# Alias para el nuevo nombre del secundario (Groq usa el mismo protocolo OpenAI).
GroqAPIError = DeepSeekAPIError
SecondaryAPIError = DeepSeekAPIError


def build_openai_tools(mcp_tools):
    tools = []
    for tool in (mcp_tools or []):
        tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or tool.name,
                "parameters": _tool_schema(tool) or {"type": "object", "properties": {}},
            },
        })
    return tools


async def run_groq_stream(
    user_message: str,
    lang: str = "es",
    context: str | None = None,
    dataset_text: str | None = None,
    style_prompt: str | None = None,
    model_choice: str | None = None,
    temperature: float | None = None,
    mode: str = "full",
    images: list | None = None,
    mcp_tools: list | None = None,
) -> AsyncIterator[str]:
    cfg = _secondary_llm_config(model_choice)
    label = cfg["label"]
    yield event("status", content=f"Conectando con {label}..." if lang == "es" else f"Connecting to {label}...")

    api_key = cfg["api_key"]
    if not api_key:
        yield event("error", content=missing_key_error_message("groq", lang))
        return

    model = cfg["model"]
    base_url = cfg["base_url"]
    allowed_tools = {tool.name for tool in (mcp_tools or [])}
    openai_tools = build_openai_tools(mcp_tools)

    first_text = user_message
    n_images = len(images or [])
    if n_images:
        first_text += (
            f"\n[User attached {n_images} image(s). IMAGE RULES: accept ONLY financial charts, graphs, "
            "tables or dashboards. Analyze them visually FIRST and reference what you see. "
            "If an image is NOT a financial graphic (meme, animal, person, landscape, random photo), "
            "do NOT break and do NOT output any HTML block: reply in 1-2 sentences explaining you can "
            "only build interfaces from financial charts/graphics, and ask for a proper one.]"
        )
        yield event("status", content=f"Analizando {n_images} imagen(es)..." if lang == "es" else f"Analyzing {n_images} image(s)...")

    lang_note = "Reply in Spanish." if lang == "es" else "Reply in English."
    system_instruction = SYSTEM_PROMPT + "\n" + lang_note
    if style_prompt:
        system_instruction += (
            "\nUser style preference for all generated interfaces "
            "(takes precedence over the default visual style): " + style_prompt[:800]
        )
    if mode == "data":
        system_instruction += (
            "\nData-only mode: call the needed MCP tools, then reply with a 1-2 sentence "
            "summary only. Do NOT output any HTML block."
        )

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": first_text},
    ]
    if context:
        messages.append({
            "role": "user",
            "content": "Previous turn summary for continuity (adapt the new interface to it when relevant): " + context[:1500],
        })
    if dataset_text:
        messages.append({"role": "user", "content": dataset_text})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as http_client:
            for _ in range(6):
                has_text = False
                payload = {
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    "temperature": 0.7 if temperature is None else temperature,
                }
                if openai_tools:
                    payload["tools"] = openai_tools
                    payload["tool_choice"] = "auto"

                tool_calls_dict = {}
                accumulated_text = ""
                finish_reason = None

                async with http_client.stream(
                    "POST",
                    f"{base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                ) as resp:
                    if resp.status_code != 200:
                        await resp.aread()
                        raise SecondaryAPIError(status_code=resp.status_code, message=f"{label} returned {resp.status_code}")

                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        data_str = line[5:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        choice = choices[0]
                        if choice.get("finish_reason"):
                            finish_reason = choice["finish_reason"]

                        delta = choice.get("delta") or {}
                        content = delta.get("content")
                        if content:
                            has_text = True
                            accumulated_text += content
                            yield event("text_chunk", content=content)

                        for tc in delta.get("tool_calls") or []:
                            idx = tc.get("index", 0)
                            if idx not in tool_calls_dict:
                                tool_calls_dict[idx] = {
                                    "id": tc.get("id") or f"call_{idx}",
                                    "name": (tc.get("function") or {}).get("name") or "",
                                    "arguments": (tc.get("function") or {}).get("arguments") or "",
                                }
                            else:
                                if tc.get("id"):
                                    tool_calls_dict[idx]["id"] = tc["id"]
                                fn = tc.get("function") or {}
                                if fn.get("name"):
                                    tool_calls_dict[idx]["name"] += fn["name"]
                                if fn.get("arguments"):
                                    tool_calls_dict[idx]["arguments"] += fn["arguments"]

                if tool_calls_dict:
                    sorted_calls = [tool_calls_dict[k] for k in sorted(tool_calls_dict.keys())]
                    assistant_msg = {
                        "role": "assistant",
                        "content": accumulated_text or None,
                        "tool_calls": [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {
                                    "name": tc["name"],
                                    "arguments": tc["arguments"],
                                },
                            }
                            for tc in sorted_calls
                        ],
                    }
                    messages.append(assistant_msg)

                    for tc in sorted_calls:
                        fn_name = tc["name"]
                        try:
                            fn_args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                        except Exception:
                            fn_args = {}

                        yield event(
                            "tool_call",
                            content=f"Fetching {fn_name.replace('_', ' ')}...",
                            tool=fn_name,
                            args=fn_args,
                        )
                        try:
                            if fn_name not in allowed_tools:
                                raise ValueError("Unknown tool")
                            data = await mcp_client.call_tool(fn_name, fn_args)
                            yield event("tool_result", tool=fn_name, data=data)
                            res_str = json.dumps(data, ensure_ascii=False)
                        except Exception:
                            err_res = {"error": "The MCP tool could not complete the request."}
                            yield event("tool_result", tool=fn_name, data=err_res, failed=True)
                            res_str = json.dumps(err_res, ensure_ascii=False)

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": res_str,
                        })

                    yield event(
                        "status",
                        content="Generando interfaz con los resultados de las herramientas..."
                        if lang == "es"
                        else "Generating interface from tool results...",
                    )
                    continue

                if finish_reason and finish_reason not in ("stop", "length", None):
                    yield event(
                        "error",
                        content=f"{label} no pudo finalizar esta respuesta. Intenta con una solicitud diferente."
                        if lang == "es"
                        else f"{label} could not finish this response. Try a shorter or different request.",
                    )
                    return

                if has_text:
                    yield event("done", content="Response complete")
                    return
                else:
                    yield event(
                        "error",
                        content=f"{label} no devolvió texto. Intenta con una solicitud diferente."
                        if lang == "es"
                        else f"{label} returned no text. Try a different request.",
                    )
                    return

            yield event(
                "error",
                content="Límite de llamadas a herramientas alcanzado. Por favor intenta con una solicitud más simple."
                if lang == "es"
                else "Tool call limit reached. Please try a simpler request.",
            )
    except Exception as error:
        yield event("error", content=groq_error_message(error, lang, label=label))


# Alias legacy para no romper imports existentes.
run_deepseek_stream = run_groq_stream


async def run_agent_stream(user_message: str, lang: str = "es", context: str | None = None,
                     dataset_text: str | None = None, style_prompt: str | None = None,
                     model_choice: str | None = None, temperature: float | None = None,
                     mode: str = "full", images: list | None = None,
                     provider: str | None = None) -> AsyncIterator[str]:
    chosen_provider = (provider or LLM_PROVIDER or "auto").strip().lower()
    if chosen_provider not in {"gemini", "groq", "deepseek", "auto"}:
        chosen_provider = "auto"
    # "deepseek" se mantiene como alias del secundario (ahora Groq).
    if chosen_provider == "deepseek":
        chosen_provider = "groq"

    mcp_tools = []
    if MCP_ENABLED:
        try:
            mcp_tools = await mcp_client.list_tools()
        except Exception:
            yield event("error", content="MCP tools are unavailable. Check the MCP server or set MCP_ENABLED=false.")
            return

    if chosen_provider == "groq":
        async for chunk in run_groq_stream(
            user_message=user_message,
            lang=lang,
            context=context,
            dataset_text=dataset_text,
            style_prompt=style_prompt,
            model_choice=model_choice,
            temperature=temperature,
            mode=mode,
            images=images,
            mcp_tools=mcp_tools,
        ):
            yield chunk
        return

    if chosen_provider == "auto" and not GEMINI_API_KEYS and _secondary_configured():
        async for chunk in run_groq_stream(
            user_message=user_message,
            lang=lang,
            context=context,
            dataset_text=dataset_text,
            style_prompt=style_prompt,
            model_choice=model_choice,
            temperature=temperature,
            mode=mode,
            images=images,
            mcp_tools=mcp_tools,
        ):
            yield chunk
        return

    # Si en modo auto se eligió explícitamente un modelo del secundario
    # (ej. openai/gpt-oss-120b en el desplegable), ir directo a Groq.
    if chosen_provider == "auto" and _is_secondary_model(model_choice) and (model_choice or "").strip() not in GEMINI_MODELS:
        async for chunk in run_groq_stream(
            user_message=user_message,
            lang=lang,
            context=context,
            dataset_text=dataset_text,
            style_prompt=style_prompt,
            model_choice=model_choice,
            temperature=temperature,
            mode=mode,
            images=images,
            mcp_tools=mcp_tools,
        ):
            yield chunk
        return

    yield event("status", content="Connecting to Gemini...")

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
    preferred = [model_choice] if model_choice and model_choice in GEMINI_MODELS else []
    ordered_models = preferred + [m for m in GEMINI_MODELS if m != model_choice]
    combos = [(key, model) for key in (GEMINI_API_KEYS or [GEMINI_API_KEY]) for model in ordered_models]

    gemini_failed_error = None
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
                        call_args = dict(call.args or {})
                        yield event("tool_call", content=f"Fetching {call.name.replace('_', ' ')}...",
                                    tool=call.name, args=call_args)
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
                yield event("error", content="Tool call limit reached. Please try a simpler request.")
                return
        except Exception as error:
            code = _extract_status_code(error)
            if code in (429, 404, 500, 502, 503, 504) and not last_combo:
                yield event("status", content="Usage limit reached, trying another model...")
                continue
            gemini_failed_error = error
            break

    if gemini_failed_error is not None:
        code = _extract_status_code(gemini_failed_error)
        FALLBACK_CODES = {429, 401, 403, 500, 502, 503}
        may_fallback = code in FALLBACK_CODES or _looks_like_quota_error(gemini_failed_error)
        if chosen_provider == "auto" and may_fallback and _secondary_configured():
            fallback_label = "Groq" if GROQ_API_KEY else "DeepSeek"
            yield event(
                "status",
                content=f"Gemini no disponible, cambiando a {fallback_label}..."
                if lang == "es"
                else f"Gemini unavailable, switching to {fallback_label}...",
            )
            async for chunk in run_groq_stream(
                user_message=user_message,
                lang=lang,
                context=context,
                dataset_text=dataset_text,
                style_prompt=style_prompt,
                model_choice=model_choice,
                temperature=temperature,
                mode=mode,
                images=images,
                mcp_tools=mcp_tools,
            ):
                yield chunk
            return
        yield event("error", content=gemini_error_message(gemini_failed_error, lang))


@app.get("/", response_class=HTMLResponse)
async def serve_index():
    return HTMLResponse((BASE_DIR / "static" / "index.html").read_text(encoding="utf-8"))


@app.post("/api/generate")
async def generate_interface(body: GenerateRequest):
    provider = (body.provider or LLM_PROVIDER or "auto").strip().lower()
    if provider not in {"gemini", "groq", "deepseek", "auto"}:
        provider = "auto"
    if provider == "deepseek":
        provider = "groq"

    if provider == "gemini" and not GEMINI_API_KEYS:
        raise HTTPException(
            status_code=503,
            detail=missing_key_error_message("gemini", body.lang),
        )
    if provider == "groq" and not _secondary_configured():
        raise HTTPException(
            status_code=503,
            detail=missing_key_error_message("groq", body.lang),
        )
    if provider == "auto" and not GEMINI_API_KEYS and not _secondary_configured():
        raise HTTPException(
            status_code=503,
            detail=missing_key_error_message("auto", body.lang),
        )

    dataset_text = load_dataset_context(body.dataset_id) if body.dataset_id else None
    images = [img.model_dump() for img in (body.images or [])]
    return StreamingResponse(run_agent_stream(body.message, body.lang, body.context, dataset_text,
                                              body.style_prompt, body.model, body.temperature, body.mode,
                                              images, body.provider),
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
            "llm_provider": LLM_PROVIDER,
            "gemini_configured": bool(GEMINI_API_KEYS), "model": GEMINI_MODEL, "models": GEMINI_MODELS,
            "groq_configured": bool(GROQ_API_KEY), "groq_model": GROQ_MODEL, "groq_models": GROQ_MODELS, "groq_base_url": GROQ_BASE_URL,
            "deepseek_configured": bool(DEEPSEEK_API_KEY), "deepseek_model": DEEPSEEK_MODEL,
            "secondary_configured": _secondary_configured(),
            "secondary_provider": "groq" if GROQ_API_KEY else ("deepseek" if DEEPSEEK_API_KEY else None),
            "mcp_enabled": MCP_ENABLED,
            "mcp_server": "finflow-financial-tools", "protocol": "A2UI over MCP"}


app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
