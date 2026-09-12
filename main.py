"""
FinFlow AI - Main FastAPI Backend
Agentic AI that generates financial web interfaces in real-time using MCP tools.
Uses the modern google-genai SDK (google.genai).
"""

import json
import os
import asyncio
import sys
from typing import AsyncIterator

from google import genai
from google.genai import types as genai_types
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="FinFlow AI", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Gemini Configuration ─────────────────────────────────────────────────────

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

SYSTEM_PROMPT = """You are FinFlow AI, an expert financial AI agent that generates beautiful, 
interactive web interfaces for financial use cases. Your specialty is creating stunning HTML/CSS/JS 
dashboards and components that display financial data in real-time.

BEHAVIOR:
1. Analyze the user's financial need in natural language.
2. Use the available MCP tools to fetch real financial data.
3. Generate a complete, beautiful HTML interface that displays that data.
4. The interface MUST use Bootstrap 5 and glassmorphism styling.
5. Use Chart.js for any charts or graphs.
6. Never use emojis anywhere in the generated HTML.
7. Make the UI professional, financial-grade, and visually stunning.

GENERATED HTML RULES:
- Always include Bootstrap 5 via CDN.
- Always include Chart.js via CDN when charts are needed.
- Use glassmorphism cards: background rgba(255,255,255,0.05), backdrop-filter blur, border rgba(255,255,255,0.1).
- Dark financial theme: background gradient from #0a0e27 to #1a1f4e.
- Accent colors: #4f8ef7 (primary), #00d4ff (secondary), #10b981 (positive), #ef4444 (negative).
- Include inline CSS within a <style> tag.
- Include all JavaScript inline within a <script> tag.
- The HTML must be a complete, self-contained document.
- Use real data from the MCP tools in the interface.
- Add smooth animations and hover effects.
- Use professional financial typography (numbers formatted with commas, 2 decimal places).
- NO emojis anywhere.

RESPONSE FORMAT:
First, briefly explain what you are building (1-2 sentences, plain text).
Then output the complete HTML document between ```html and ``` markers."""


# ─── MCP Client ───────────────────────────────────────────────────────────────

class MCPFinancialClient:
    """Manages connection to the MCP financial tools server."""

    def __init__(self):
        self.server_script = os.path.join(os.path.dirname(__file__), "mcp_server.py")
        self._tools_cache = None

    async def get_tools_and_call(self, tool_name: str, tool_args: dict) -> str:
        """Call a specific MCP tool and return the result as JSON string."""
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_script],
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, tool_args)
                if result.content:
                    return result.content[0].text
                return "{}"

    async def list_tools(self) -> list:
        """List available MCP tools."""
        if self._tools_cache:
            return self._tools_cache
        server_params = StdioServerParameters(
            command=sys.executable,
            args=[self.server_script],
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                self._tools_cache = tools_result.tools
                return self._tools_cache


mcp_client = MCPFinancialClient()


# ─── Gemini + MCP Agent ───────────────────────────────────────────────────────

def build_gemini_tools(mcp_tools: list) -> list[genai_types.Tool]:
    """Convert MCP tool schemas to Gemini Tool declarations."""
    function_declarations = []

    for tool in mcp_tools:
        params = {}
        required = []
        if tool.input_schema and "properties" in tool.input_schema:
            for prop_name, prop_schema in tool.input_schema["properties"].items():
                ptype = prop_schema.get("type", "string")
                schema_kwargs = {
                    "description": prop_schema.get("description", prop_schema.get("title", prop_name)),
                }
                if ptype == "array":
                    schema_kwargs["type"] = "ARRAY"
                    items_type = prop_schema.get("items", {}).get("type", "string").upper()
                    schema_kwargs["items"] = genai_types.Schema(type=items_type)
                elif ptype == "integer":
                    schema_kwargs["type"] = "INTEGER"
                elif ptype == "number":
                    schema_kwargs["type"] = "NUMBER"
                elif ptype == "boolean":
                    schema_kwargs["type"] = "BOOLEAN"
                else:
                    schema_kwargs["type"] = "STRING"
                params[prop_name] = genai_types.Schema(**schema_kwargs)
            required = tool.input_schema.get("required", [])

        fd = genai_types.FunctionDeclaration(
            name=tool.name,
            description=tool.description or tool.name,
            parameters=genai_types.Schema(
                type="OBJECT",
                properties=params,
                required=required,
            ) if params else None,
        )
        function_declarations.append(fd)

    return [genai_types.Tool(function_declarations=function_declarations)]


async def run_agent_stream(user_message: str) -> AsyncIterator[str]:
    """
    Run the FinFlow AI agent with MCP tools and stream the response.
    Yields SSE-formatted event chunks.
    """
    # 1. Get available MCP tools
    try:
        mcp_tools = await mcp_client.list_tools()
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': f'MCP connection failed: {str(e)}'})}\n\n"
        return

    gemini_tools = build_gemini_tools(mcp_tools)

    # 2. Initialize Gemini client (new SDK)
    client = genai.Client(api_key=GEMINI_API_KEY)

    contents: list[genai_types.Content] = [
        genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=user_message)],
        )
    ]

    config = genai_types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=gemini_tools,
        temperature=0.7,
    )

    yield f"data: {json.dumps({'type': 'status', 'content': 'Analyzing your financial request...'})}\n\n"
    await asyncio.sleep(0.05)

    # 3. Agentic tool-call loop
    max_iterations = 6
    for iteration in range(max_iterations):
        try:
            response = await asyncio.to_thread(
                client.models.generate_content,
                model="gemini-2.0-flash",
                contents=contents,
                config=config,
            )
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': f'Gemini API error: {str(e)}'})}\n\n"
            return

        # Collect function calls from response
        function_calls = []
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if part.function_call:
                    function_calls.append(part.function_call)

        if not function_calls:
            # No more tool calls — extract final text
            final_text = ""
            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if part.text:
                        final_text += part.text
            break

        # Append model response to history
        contents.append(response.candidates[0].content)

        # Execute tool calls via MCP
        tool_response_parts = []
        for fc in function_calls:
            tool_name = fc.name
            tool_args = dict(fc.args) if fc.args else {}

            tool_display = tool_name.replace("_", " ")
            yield f"data: {json.dumps({'type': 'tool_call', 'content': f'Fetching {tool_display}...'})}\n\n"
            await asyncio.sleep(0.05)

            try:
                result_str = await mcp_client.get_tools_and_call(tool_name, tool_args)
                result_data = json.loads(result_str)

                yield f"data: {json.dumps({'type': 'tool_result', 'tool': tool_name, 'data': result_data})}\n\n"
                await asyncio.sleep(0.05)

                tool_response_parts.append(
                    genai_types.Part(
                        function_response=genai_types.FunctionResponse(
                            name=tool_name,
                            response={"result": result_data},
                        )
                    )
                )
            except Exception as e:
                tool_response_parts.append(
                    genai_types.Part(
                        function_response=genai_types.FunctionResponse(
                            name=tool_name,
                            response={"error": str(e)},
                        )
                    )
                )

        # Append tool results to conversation
        contents.append(
            genai_types.Content(role="tool", parts=tool_response_parts)
        )

        yield f"data: {json.dumps({'type': 'status', 'content': 'Generating interface...'})}\n\n"
        await asyncio.sleep(0.05)

    else:
        # Max iterations reached
        final_text = "Maximum tool call iterations reached. Please try a simpler request."

    if not final_text:
        yield f"data: {json.dumps({'type': 'error', 'content': 'No response generated. Check your Gemini API key.'})}\n\n"
        return

    # 4. Stream the final text in chunks
    yield f"data: {json.dumps({'type': 'status', 'content': 'Streaming interface code...'})}\n\n"
    await asyncio.sleep(0.05)

    chunk_size = 40
    for i in range(0, len(final_text), chunk_size):
        chunk = final_text[i:i + chunk_size]
        yield f"data: {json.dumps({'type': 'text_chunk', 'content': chunk})}\n\n"
        await asyncio.sleep(0.01)

    yield f"data: {json.dumps({'type': 'done', 'content': 'Interface generation complete'})}\n\n"


# ─── API Routes ───────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_index():
    """Serve the main FinFlow AI interface."""
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.post("/api/generate")
async def generate_interface(request: Request):
    """Stream the AI agent response for a financial interface generation request."""
    body = await request.json()
    user_message = body.get("message", "").strip()

    if not user_message:
        return {"error": "Message is required"}

    if not GEMINI_API_KEY:
        async def error_stream():
            yield f"data: {json.dumps({'type': 'error', 'content': 'GEMINI_API_KEY not configured. Please add it to your .env file.'})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    return StreamingResponse(
        run_agent_stream(user_message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/tools")
async def list_tools():
    """List available MCP financial tools."""
    try:
        tools = await mcp_client.list_tools()
        return {
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                }
                for t in tools
            ]
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/health")
async def health():
    return {"status": "ok", "service": "FinFlow AI", "version": "1.0.0"}


# ─── Static Files ─────────────────────────────────────────────────────────────

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
