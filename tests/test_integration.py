import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from google.genai import types

import main


def response(*parts, finish_reason=types.FinishReason.STOP):
    return types.GenerateContentResponse(candidates=[types.Candidate(
        content=types.Content(role="model", parts=list(parts)), finish_reason=finish_reason,
    )])


class FakeClient:
    def __init__(self, rounds):
        self.rounds = iter(rounds)
        self.calls = []
        self.aio = self
        self.models = self
        self.closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.closed = True

    async def generate_content_stream(self, **kwargs):
        self.calls.append({**kwargs, "contents": list(kwargs["contents"])})
        chunks = next(self.rounds)

        async def stream():
            for chunk in chunks:
                if isinstance(chunk, Exception):
                    raise chunk
                yield chunk
        return stream()


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.key = patch.object(main, "GEMINI_API_KEY", "test-key-never-public")
        self.mcp = patch.object(main, "MCP_ENABLED", False)
        self.key.start()
        self.mcp.start()
        self.addCleanup(self.key.stop)
        self.addCleanup(self.mcp.stop)

    def generate(self, fake, message="Generate a KPI card"):
        with patch.object(main.genai, "Client", return_value=fake):
            result = self.client.post("/api/generate", json={"message": message})
        self.assertEqual(result.status_code, 200)
        self.assertIn("text/event-stream", result.headers["content-type"])
        return [json.loads(frame[6:]) for frame in result.text.strip().split("\n\n")]

    def test_ui_and_health_do_not_expose_key(self):
        for url in ("/", "/health", "/static/app.js"):
            result = self.client.get(url)
            self.assertEqual(result.status_code, 200)
            self.assertNotIn("test-key-never-public", result.text)
        health = self.client.get("/health").json()
        self.assertTrue(health["gemini_configured"])
        self.assertFalse(health["mcp_enabled"])

    def test_invalid_messages(self):
        for value in ("", "   ", "x" * 501, None, 123, []):
            with self.subTest(value=type(value).__name__):
                self.assertEqual(self.client.post("/api/generate", json={"message": value}).status_code, 422)
        self.assertEqual(self.client.post("/api/generate", json={}).status_code, 422)

    def test_missing_key(self):
        with patch.object(main, "GEMINI_API_KEY", ""):
            self.assertEqual(self.client.post("/api/generate", json={"message": "Hola"}).status_code, 503)

    def test_real_sse_contract_without_mcp(self):
        html = '```html\n<html><body>Utilidad: $482,300</body></html>\n```'
        fake = FakeClient([[response(types.Part(text="Aquí está.\n")), response(types.Part(text=html))]])
        with patch.object(main.mcp_client, "list_tools", new_callable=AsyncMock) as tools:
            events = self.generate(fake, "  Generate a card  ")
            tools.assert_not_called()
        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual("".join(e["content"] for e in events if e["type"] == "text_chunk"), "Aquí está.\n" + html)
        self.assertEqual(fake.calls[0]["model"], main.GEMINI_MODEL)
        self.assertEqual(fake.calls[0]["contents"][0].parts[0].text, "Generate a card")
        self.assertTrue(fake.closed)
        self.assertEqual(self.client.get("/api/tools").json(), {"enabled": False, "tools": [], "servers": []})

    def test_error_is_sanitized_and_has_no_done(self):
        fake = FakeClient([[RuntimeError("test-key-never-public internal request")]])
        events = self.generate(fake)
        self.assertEqual(events[-1]["type"], "error")
        self.assertNotIn("test-key-never-public", json.dumps(events))
        self.assertNotIn("done", [e["type"] for e in events])
        self.assertTrue(fake.closed)

    def test_partial_stream_error(self):
        fake = FakeClient([[response(types.Part(text="Partial")), RuntimeError("connection dropped")]])
        events = self.generate(fake)
        self.assertIn("text_chunk", [e["type"] for e in events])
        self.assertEqual(events[-1]["type"], "error")

    def test_no_text_and_truncated_response_are_errors(self):
        cases = [types.GenerateContentResponse(), response(types.Part(text="partial"), finish_reason=types.FinishReason.MAX_TOKENS)]
        for chunk in cases:
            events = self.generate(FakeClient([[chunk]]))
            self.assertEqual(events[-1]["type"], "error")

    def test_mcp_failure_is_explicit(self):
        with patch.object(main, "MCP_ENABLED", True), patch.object(main.mcp_client, "list_tools", new_callable=AsyncMock, side_effect=RuntimeError("secret")):
            events = self.generate(FakeClient([]))
            self.assertEqual(events[-1]["type"], "error")
            self.assertNotIn("secret", json.dumps(events))
            self.assertEqual(self.client.get("/api/tools").status_code, 503)

    def test_mcp_tool_result_returns_to_gemini_with_signature(self):
        tool = SimpleNamespace(name="get_stock_quote", description="Demo quote", inputSchema={
            "type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"],
        })
        part = types.Part(function_call=types.FunctionCall(name=tool.name, args={"symbol": "AAPL"}), thought_signature=b"signature")
        fake = FakeClient([[response(part)], [response(types.Part(text="Demo quote: 100"))]])
        with patch.object(main, "MCP_ENABLED", True), patch.object(main.mcp_client, "list_tools", new_callable=AsyncMock, return_value=[tool]), patch.object(main.mcp_client, "call_tool", new_callable=AsyncMock, return_value={"price": 100}) as call:
            events = self.generate(fake)
            call.assert_awaited_once_with("get_stock_quote", {"symbol": "AAPL"})
        self.assertEqual(events[-1]["type"], "done")
        self.assertIn("tool_result", [e["type"] for e in events])
        history = fake.calls[1]["contents"]
        self.assertEqual(history[1].parts[0].thought_signature, b"signature")
        self.assertEqual(history[2].parts[0].function_response.response, {"result": {"price": 100}})


class MCPAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_bundled_mcp_lists_tools_and_executes_calculation(self):
        client = main.MCPFinancialClient()
        tools = await client.list_tools()
        self.assertIn("get_stock_quote", [tool.name for tool in tools])
        self.assertTrue(main.build_gemini_tools(tools))
        result = await client.call_tool("get_stock_quote", {"symbol": "AAPL"})
        self.assertEqual(result["symbol"], "AAPL")
        self.assertIsInstance(result["price"], (int, float))


class MultiServerTests(unittest.IsolatedAsyncioTestCase):
    def demo_tool(self):
        return SimpleNamespace(name="get_stock_quote", description="Demo quote", inputSchema={
            "type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"],
        })

    def live_tool(self):
        return SimpleNamespace(name="get_live_quote", description="Live quote", input_schema={
            "type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"],
        })

    async def test_config_lists_demo_and_live(self):
        self.assertEqual([s["name"] for s in main.MCP_SERVERS], ["demo", "live"])

    async def test_routing_and_grouping(self):
        demo, live = self.demo_tool(), self.live_tool()

        async def fake_request(client_self, server, tool_name=None, tool_args=None):
            if tool_name is None:
                return [demo] if server["name"] == "demo" else [live]
            return {"ok": server["name"]}

        client = main.MCPFinancialClient()
        with patch.object(main.MCPFinancialClient, "_request", autospec=True, side_effect=fake_request):
            tools = await client.list_tools()
            self.assertEqual([t.name for t in tools], ["get_stock_quote", "get_live_quote"])
            groups = await client.list_tools_by_server()
            self.assertEqual([(g["name"], [t.name for t in g["tools"]]) for g in groups],
                             [("demo", ["get_stock_quote"]), ("live", ["get_live_quote"])])
            self.assertEqual(await client.call_tool("get_live_quote", {"symbol": "AAPL"}), {"ok": "live"})
            self.assertEqual(await client.call_tool("get_stock_quote", {"symbol": "AAPL"}), {"ok": "demo"})
            self.assertEqual(len(main.build_gemini_tools(tools)[0].function_declarations), 2)

    def test_api_tools_groups_by_server(self):
        groups = [
            {"name": "demo", "label": "Demo", "tools": [self.demo_tool()]},
            {"name": "live", "label": "Live", "tools": [self.live_tool()]},
        ]
        client = TestClient(main.app)
        with patch.object(main, "MCP_ENABLED", True), patch.object(
                main.mcp_client, "list_tools_by_server", new_callable=AsyncMock, return_value=groups):
            body = client.get("/api/tools").json()
        self.assertTrue(body["enabled"])
        self.assertEqual([s["name"] for s in body["servers"]], ["demo", "live"])
        self.assertEqual([(t["name"], t["server"]) for t in body["tools"]],
                         [("get_stock_quote", "demo"), ("get_live_quote", "live")])


if __name__ == "__main__":
    unittest.main()