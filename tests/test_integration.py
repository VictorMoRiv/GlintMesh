import json
import unittest
from pathlib import Path
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
        with patch.object(main, "GEMINI_API_KEY", ""), patch.object(main, "GEMINI_API_KEYS", []):
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

    def test_context_is_optional_and_appends_to_history(self):
        html = '```html\n<html><body>ok</body></html>\n```'
        fake = FakeClient([[response(types.Part(text=html))]])
        with patch.object(main.genai, "Client", return_value=fake):
            result = self.client.post("/api/generate", json={"message": "Ajusta el dashboard", "context": "Previous: portfolio AAPL"})
        self.assertEqual(result.status_code, 200)
        history = fake.calls[0]["contents"]
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].parts[0].text, "Ajusta el dashboard")
        self.assertIn("Previous: portfolio AAPL", history[1].parts[0].text)

    def test_invalid_context(self):
        self.assertEqual(self.client.post("/api/generate", json={"message": "Hi", "context": "x" * 2001}).status_code, 422)
        result = self.client.post("/api/generate", json={"message": "Hi", "context": "   "})
        self.assertEqual(result.status_code, 200)

    def test_quota_falls_back_to_next_model(self):
        class QuotaError(RuntimeError):
            code = 429

        html = '```html\n<html><body>ok</body></html>\n```'
        fake = FakeClient([[QuotaError("quota")], [response(types.Part(text=html))]])
        with patch.object(main, "GEMINI_MODELS", ["model-a", "model-b"]), patch.object(main.genai, "Client", return_value=fake):
            result = self.client.post("/api/generate", json={"message": "Hi"})
        self.assertEqual(result.status_code, 200)
        events = [json.loads(frame[6:]) for frame in result.text.strip().split("\n\n")]
        self.assertEqual([c["model"] for c in fake.calls], ["model-a", "model-b"])
        self.assertIn("status", [e["type"] for e in events])
        self.assertEqual(events[-1]["type"], "done")

    def test_style_prompt_reaches_system_instruction(self):
        fake = FakeClient([[response(types.Part(text="ok"))]])
        with patch.object(main.genai, "Client", return_value=fake):
            result = self.client.post("/api/generate", json={"message": "Hi", "style_prompt": "Dark neon style"})
        self.assertEqual(result.status_code, 200)
        config = fake.calls[0]["config"]
        self.assertIn("Dark neon style", config.system_instruction)
        self.assertEqual(self.client.post("/api/generate", json={"message": "Hi", "style_prompt": "x" * 1001}).status_code, 422)

    def test_generation_options_validated_and_forwarded(self):
        fake = FakeClient([[response(types.Part(text="ok"))]])
        with patch.object(main, "GEMINI_MODELS", ["model-a", "model-b"]), patch.object(main.genai, "Client", return_value=fake):
            result = self.client.post("/api/generate", json={"message": "Hi", "model": "model-b", "temperature": 0.2, "mode": "data"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(fake.calls[0]["model"], "model-b")
        self.assertEqual(fake.calls[0]["config"].temperature, 0.2)
        self.assertIn("Data-only mode", fake.calls[0]["config"].system_instruction)
        for bad in ({"model": "nope"}, {"temperature": 2}, {"temperature": -1}, {"mode": "turbo"}):
            with self.subTest(bad=bad):
                self.assertEqual(self.client.post("/api/generate", json={"message": "Hi", **bad}).status_code, 422)

    def test_direct_tool_call(self):
        tool = SimpleNamespace(name="get_live_quote", description="Live", input_schema={})
        with patch.object(main, "MCP_ENABLED", True), patch.object(
                main.mcp_client, "list_tools", new_callable=AsyncMock, return_value=[tool]), patch.object(
                main.mcp_client, "call_tool", new_callable=AsyncMock, return_value={"price": 1}) as call:
            result = self.client.post("/api/tool-call", json={"tool": "get_live_quote", "args": {"symbol": "AAPL"}})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json(), {"tool": "get_live_quote", "data": {"price": 1}})
            call.assert_awaited_once_with("get_live_quote", {"symbol": "AAPL"})
            self.assertEqual(self.client.post("/api/tool-call", json={"tool": "nope", "args": {}}).status_code, 404)
        self.assertEqual(self.client.post("/api/tool-call", json={"tool": "get_live_quote", "args": {}}).status_code, 503)

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
        self.assertEqual([s["name"] for s in main.MCP_SERVERS], ["demo", "live", "ecb"])

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
                             [("demo", ["get_stock_quote"]), ("live", ["get_live_quote"]), ("ecb", ["get_live_quote"])])
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


class FixtureSchemaTests(unittest.TestCase):
    """Golden MCP payloads are the shared truth base: A2UI renders exactly these shapes."""

    REQUIRED = {
        "get_live_quote": {"symbol", "price", "change", "change_percent", "volume", "timestamp", "source"},
        "get_live_history": {"symbol", "period_days", "data", "start_price", "end_price", "total_return", "source"},
        "get_live_indices": {"SP500", "NASDAQ", "DOW", "IPC", "source"},
        "get_live_fx": {"base", "timestamp", "rates", "source"},
        "get_stock_quote": {"symbol", "price", "change", "change_percent", "volume", "timestamp"},
        "get_portfolio_summary": {"total_market_value", "total_unrealized_gain", "positions"},
        "get_market_indices": {"SP500", "NASDAQ", "DOW", "IPC"},
        "get_historical_prices": {"symbol", "period_days", "data", "start_price", "end_price", "total_return"},
        "get_financial_news": None,  # list of {title, sentiment, source}
        "analyze_credit_risk": {"risk_score", "recommendation", "debt_to_income_ratio"},
        "calculate_compound_interest": {"final_balance", "total_contributions", "yearly_breakdown"},
        "get_forex_rates": {"base", "timestamp", "rates"},
    }

    def test_fixtures_match_a2ui_contract(self):
        path = Path(__file__).resolve().parent / "fixtures" / "mcp_samples.json"
        samples = json.loads(path.read_text(encoding="utf-8"))
        for tool, required in self.REQUIRED.items():
            with self.subTest(tool=tool):
                self.assertIn(tool, samples)
                payload = samples[tool]
                if required is None:
                    self.assertIsInstance(payload, list)
                    self.assertTrue(payload)
                    for item in payload:
                        self.assertIn("title", item)
                        self.assertIn("sentiment", item)
                else:
                    self.assertTrue(required <= set(payload), f"{tool} missing {required - set(payload)}")
        live = samples["get_live_quote"]
        self.assertEqual(live["source"], "live")
        self.assertEqual(live["symbol"], "AAPL")
        self.assertIsInstance(live["price"], (int, float))


class DatasetTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.key = patch.object(main, "GEMINI_API_KEY", "test-key-never-public")
        self.mcp = patch.object(main, "MCP_ENABLED", False)
        self.key.start()
        self.mcp.start()
        self.addCleanup(self.key.stop)
        self.addCleanup(self.mcp.stop)
        for path in main.UPLOAD_DIR.glob("test_*"):
            path.unlink(missing_ok=True)

    def upload(self, name, content, ctype="text/csv"):
        return self.client.post("/api/datasets", files={"file": (name, content, ctype)})

    def test_upload_csv_and_list(self):
        body = "symbol,shares\nAAPL,10\nMSFT,5\n"
        result = self.upload("test_portfolio.csv", body)
        self.assertEqual(result.status_code, 200)
        data = result.json()
        self.assertEqual(data["columns"], ["symbol", "shares"])
        self.assertEqual(data["n_rows"], 2)
        listed = self.client.get("/api/datasets").json()["datasets"]
        self.assertIn(data["id"], [d["id"] for d in listed])

    def test_upload_rejects_bad_files(self):
        self.assertEqual(self.upload("test_x.exe", "hi").status_code, 415)
        self.assertEqual(self.upload("test_empty.csv", "").status_code, 413)
        bad = self.client.post("/api/datasets", files={"file": ("test_bad.json", "{nope", "application/json")})
        self.assertEqual(bad.status_code, 422)

    def test_generate_with_dataset_reaches_gemini(self):
        data = self.upload("test_quotes.csv", "symbol,price\nAAPL,300\n").json()
        fake = FakeClient([[response(types.Part(text="ok"))]])
        with patch.object(main.genai, "Client", return_value=fake):
            result = self.client.post("/api/generate", json={"message": "Grafica esto", "dataset_id": data["id"]})
        self.assertEqual(result.status_code, 200)
        history = fake.calls[0]["contents"]
        self.assertEqual(len(history), 2)
        self.assertIn("test_quotes", history[1].parts[0].text)
        self.assertIn("AAPL", history[1].parts[0].text)

    def test_generate_unknown_dataset_is_404(self):
        result = self.client.post("/api/generate", json={"message": "Hi", "dataset_id": "nope_nope"})
        self.assertEqual(result.status_code, 404)

    def test_share_roundtrip(self):
        html = "<html><body>" + "x" * 200 + "</body></html>"
        result = self.client.post("/api/share", json={"html": html})
        self.assertEqual(result.status_code, 200)
        share_id = result.json()["id"]
        page = self.client.get(f"/share/{share_id}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("x" * 200, page.text)
        self.assertEqual(self.client.get("/share/nope").status_code, 404)
        self.assertEqual(self.client.post("/api/share", json={"html": "tiny"}).status_code, 422)

    def test_delete_dataset(self):
        data = self.upload("test_gone.csv", "a\n1\n").json()
        self.assertEqual(self.client.delete(f"/api/datasets/{data['id']}").status_code, 200)
        self.assertEqual(self.client.delete(f"/api/datasets/{data['id']}").status_code, 404)
        self.assertEqual(self.client.delete("/api/datasets/../main").status_code, 404)


class ImagePromptTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)

    def test_images_validated(self):
        import base64
        blob = base64.b64encode(b"x" * 200).decode()
        good = {"message": "Mira esta grafica", "images": [{"mime": "image/png", "data": blob}]}
        with patch.object(main, "GEMINI_API_KEYS", ["k"]), patch.object(
                main.genai, "Client", return_value=FakeClient([[response(types.Part(text="ok"))]])):
            self.assertEqual(self.client.post("/api/generate", json=good).status_code, 200)
        bad_mime = {"message": "Hi", "images": [{"mime": "image/svg+xml", "data": blob}]}
        self.assertEqual(self.client.post("/api/generate", json=bad_mime).status_code, 422)
        too_many = {"message": "Hi", "images": [{"mime": "image/png", "data": blob}] * 4}
        self.assertEqual(self.client.post("/api/generate", json=too_many).status_code, 422)

    def test_image_bytes_reach_gemini(self):
        import base64
        blob = base64.b64encode(b"fakepng" * 30).decode()
        fake = FakeClient([[response(types.Part(text="visto"))]])
        with patch.object(main, "GEMINI_API_KEYS", ["k"]), patch.object(main.genai, "Client", return_value=fake):
            result = self.client.post("/api/generate", json={"message": "Describe", "images": [{"mime": "image/png", "data": blob}]})
        self.assertEqual(result.status_code, 200)
        parts = fake.calls[0]["contents"][0].parts
        self.assertEqual(parts[0].text, "Describe")
        self.assertTrue(any(getattr(p, "inline_data", None) is not None for p in parts[1:]))


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        main._save_users({})

    def tearDown(self):
        main._save_users({})

    def test_register_login_me_logout(self):
        self.assertEqual(self.client.post("/api/auth/register", json={"user": "jack", "password": "secret1"}).status_code, 200)
        self.assertEqual(self.client.post("/api/auth/register", json={"user": "jack", "password": "secret1"}).status_code, 409)
        login = self.client.post("/api/auth/login", json={"user": "jack", "password": "secret1"}).json()
        self.assertIn("token", login)
        me = self.client.get("/api/auth/me", headers={"Authorization": "Bearer " + login["token"]}).json()
        self.assertEqual(me, {"user": "jack"})
        self.assertEqual(self.client.get("/api/auth/me").json(), {"user": None})
        self.assertEqual(self.client.post("/api/auth/login", json={"user": "jack", "password": "nope"}).status_code, 401)
        self.assertEqual(self.client.post("/api/auth/logout", json={"token": login["token"]}).status_code, 200)
        self.assertEqual(self.client.get("/api/auth/me", headers={"Authorization": "Bearer " + login["token"]}).json(), {"user": None})

    def test_passwords_are_hashed(self):
        self.client.post("/api/auth/register", json={"user": "ana", "password": "secret2"})
        stored = main._load_users()["ana"]
        self.assertNotIn("secret2", json.dumps(stored))
        self.assertIn("hash", stored)


if __name__ == "__main__":
    unittest.main()