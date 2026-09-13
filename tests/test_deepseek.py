"""Tests for DeepSeek LLM integration, fallback mechanism, security, and MCP support."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient
from google.genai import types

import main


class FakeStreamResponse:
    def __init__(self, lines, status_code=200):
        self.lines = lines
        self.status_code = status_code

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def aiter_lines(self):
        for line in self.lines:
            yield line

    async def aread(self):
        return b'{"error": "Simulated error from DeepSeek"}'


class FakeAsyncClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.call_idx = 0
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    def stream(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        if self.call_idx < len(self.responses):
            resp = self.responses[self.call_idx]
            self.call_idx += 1
            return resp
        raise RuntimeError("No more mocked responses available in FakeAsyncClient")


def make_text_chunk(text, finish_reason=None):
    payload = {
        "id": "chatcmpl-test",
        "choices": [
            {
                "index": 0,
                "delta": {"content": text},
                "finish_reason": finish_reason,
            }
        ]
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}"


def make_tool_call_chunks(call_id, tool_name, args_dict):
    args_json = json.dumps(args_dict)
    payload = {
        "id": "chatcmpl-tool",
        "choices": [
            {
                "index": 0,
                "delta": {
                    "tool_calls": [
                        {
                            "index": 0,
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": args_json,
                            }
                        }
                    ]
                },
                "finish_reason": "tool_calls",
            }
        ]
    }
    return [f"data: {json.dumps(payload, ensure_ascii=False)}", "data: [DONE]"]


class DeepSeekIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.gemini_key = "test-gemini-key-secret-12345"
        self.deepseek_key = "test-deepseek-key-secret-67890"
        self.groq_key = "test-groq-key-secret-abcde"

        self.p_gemini_key = patch.object(main, "GEMINI_API_KEY", self.gemini_key)
        self.p_gemini_keys = patch.object(main, "GEMINI_API_KEYS", [self.gemini_key])
        self.p_deepseek_key = patch.object(main, "DEEPSEEK_API_KEY", self.deepseek_key)
        self.p_deepseek_model = patch.object(main, "DEEPSEEK_MODEL", "deepseek-chat")
        # Por defecto los tests legacy aíslan Groq para no depender del .env real.
        self.p_groq_key = patch.object(main, "GROQ_API_KEY", "")
        self.p_groq_model = patch.object(main, "GROQ_MODEL", "openai/gpt-oss-120b")
        self.p_provider = patch.object(main, "LLM_PROVIDER", "deepseek")
        self.p_mcp = patch.object(main, "MCP_ENABLED", False)

        self.p_gemini_key.start()
        self.p_gemini_keys.start()
        self.p_deepseek_key.start()
        self.p_deepseek_model.start()
        self.p_groq_key.start()
        self.p_groq_model.start()
        self.p_provider.start()
        self.p_mcp.start()

        self.addCleanup(self.p_gemini_key.stop)
        self.addCleanup(self.p_gemini_keys.stop)
        self.addCleanup(self.p_deepseek_key.stop)
        self.addCleanup(self.p_deepseek_model.stop)
        self.addCleanup(self.p_groq_key.stop)
        self.addCleanup(self.p_groq_model.stop)
        self.addCleanup(self.p_provider.stop)
        self.addCleanup(self.p_mcp.stop)

    def parse_sse(self, response_text):
        events = []
        for frame in response_text.strip().split("\n\n"):
            if frame.startswith("data: "):
                events.append(json.loads(frame[6:]))
        return events

    def test_deepseek_responds_correctly(self):
        """DeepSeek responds correctly with OpenAI-compatible streaming chunks."""
        html_code = "```html\n<div>DeepSeek Financial Dashboard</div>\n```"
        lines = [
            make_text_chunk("Generando interfaz... "),
            make_text_chunk(html_code, finish_reason="stop"),
            "data: [DONE]",
        ]
        fake_client = FakeAsyncClient([FakeStreamResponse(lines, status_code=200)])

        with patch("httpx.AsyncClient", return_value=fake_client):
            res = self.client.post("/api/generate", json={"message": "Crea un dashboard financiero", "lang": "es"})

        self.assertEqual(res.status_code, 200)
        self.assertIn("text/event-stream", res.headers["content-type"])
        events = self.parse_sse(res.text)

        event_types = [e["type"] for e in events]
        self.assertIn("status", event_types)
        self.assertIn("text_chunk", event_types)
        self.assertEqual(events[-1]["type"], "done")

        full_text = "".join(e["content"] for e in events if e["type"] == "text_chunk")
        self.assertIn("DeepSeek Financial Dashboard", full_text)

        # Verify DeepSeek endpoint and authorization header
        self.assertEqual(len(fake_client.calls), 1)
        call = fake_client.calls[0]
        self.assertEqual(call["url"], "https://api.deepseek.com/chat/completions")
        self.assertEqual(call["headers"]["Authorization"], f"Bearer {self.deepseek_key}")
        self.assertEqual(call["json"]["model"], "deepseek-chat")

    def test_fallback_from_gemini_to_deepseek(self):
        """In auto mode, if Gemini returns 429, 401, 403, 500, 502, or 503, fallback to DeepSeek."""
        for code in (429, 401, 403, 500, 502, 503):
            with self.subTest(code=code):
                class MockGeminiError(RuntimeError):
                    pass
                err = MockGeminiError(f"Gemini failed with status {code}")
                err.code = code

                # Gemini fake client that raises error
                class FailingGeminiClient:
                    def __init__(self):
                        self.aio = self
                        self.models = self

                    async def __aenter__(self):
                        return self

                    async def __aexit__(self, *args):
                        pass

                    async def generate_content_stream(self, **kwargs):
                        raise err

                # DeepSeek fake client that succeeds
                lines = [
                    make_text_chunk("Respuesta generada vía DeepSeek fallback."),
                    "data: [DONE]",
                ]
                fake_http = FakeAsyncClient([FakeStreamResponse(lines, status_code=200)])

                with patch.object(main, "LLM_PROVIDER", "auto"), \
                     patch.object(main.genai, "Client", return_value=FailingGeminiClient()), \
                     patch("httpx.AsyncClient", return_value=fake_http):
                    res = self.client.post("/api/generate", json={"message": "Generar KPI", "lang": "es"})

                self.assertEqual(res.status_code, 200)
                events = self.parse_sse(res.text)

                # Status must show fallback occurred (Groq es el secundario; DeepSeek queda como alias legacy)
                status_contents = [e["content"] for e in events if e["type"] == "status"]
                self.assertTrue(any("cambiando a Groq" in s or "switching to Groq" in s or "cambiando a DeepSeek" in s or "switching to DeepSeek" in s for s in status_contents))

                # Done must be reached via DeepSeek
                self.assertEqual(events[-1]["type"], "done")
                full_text = "".join(e["content"] for e in events if e["type"] == "text_chunk")
                self.assertIn("DeepSeek fallback", full_text)

    def test_keys_never_appear_in_responses(self):
        """API keys are never exposed in health, SSE stream, or error messages."""
        # 1. Health endpoint
        health_res = self.client.get("/health")
        self.assertEqual(health_res.status_code, 200)
        self.assertNotIn(self.gemini_key, health_res.text)
        self.assertNotIn(self.deepseek_key, health_res.text)

        # 2. DeepSeek error containing leaked key in raw upstream body
        leaked_body = f"Error with key {self.deepseek_key} internal details"
        fake_http = FakeAsyncClient([FakeStreamResponse([], status_code=401)])

        with patch("httpx.AsyncClient", return_value=fake_http):
            res = self.client.post("/api/generate", json={"message": "Test leak", "lang": "es"})

        self.assertNotIn(self.deepseek_key, res.text)
        self.assertNotIn(self.gemini_key, res.text)
        events = self.parse_sse(res.text)
        self.assertEqual(events[-1]["type"], "error")
        self.assertNotIn(self.deepseek_key, json.dumps(events))

        # 3. Gemini error containing leaked key
        with patch.object(main, "LLM_PROVIDER", "gemini"):
            class GeminiLeakyError(RuntimeError):
                pass
            g_err = GeminiLeakyError(f"Leaked {self.gemini_key}")
            g_err.code = 500

            class FailingGeminiClient:
                def __init__(self):
                    self.aio = self
                    self.models = self

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

                async def generate_content_stream(self, **kwargs):
                    raise g_err

            with patch.object(main.genai, "Client", return_value=FailingGeminiClient()):
                res = self.client.post("/api/generate", json={"message": "Test gemini leak", "lang": "es"})

            self.assertNotIn(self.gemini_key, res.text)
            self.assertNotIn(self.deepseek_key, res.text)

    def test_mcp_works_with_deepseek(self):
        """MCP tools (including financial and database tools) work seamlessly with DeepSeek."""
        tool = SimpleNamespace(
            name="get_stock_quote",
            description="Fetch simulated or live quote",
            inputSchema={
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            }
        )

        # Round 1: DeepSeek calls get_stock_quote tool
        round1_lines = make_tool_call_chunks("call_abc123", "get_stock_quote", {"symbol": "NVDA"})
        # Round 2: DeepSeek completes with HTML using tool data
        round2_lines = [
            make_text_chunk("```html\n<div>NVDA Price: $120.50</div>\n```", finish_reason="stop"),
            "data: [DONE]",
        ]

        fake_http = FakeAsyncClient([
            FakeStreamResponse(round1_lines, status_code=200),
            FakeStreamResponse(round2_lines, status_code=200),
        ])

        with patch.object(main, "MCP_ENABLED", True), \
             patch.object(main.mcp_client, "list_tools", new_callable=AsyncMock, return_value=[tool]), \
             patch.object(main.mcp_client, "call_tool", new_callable=AsyncMock, return_value={"symbol": "NVDA", "price": 120.50}) as mock_call, \
             patch("httpx.AsyncClient", return_value=fake_http):
            res = self.client.post("/api/generate", json={"message": "Precio de NVDA", "lang": "es"})

        self.assertEqual(res.status_code, 200)
        events = self.parse_sse(res.text)

        # Verify tool was called through MCP client
        mock_call.assert_awaited_once_with("get_stock_quote", {"symbol": "NVDA"})

        # Verify SSE events contract: tool_call, tool_result, text_chunk, done
        event_types = [e["type"] for e in events]
        self.assertIn("tool_call", event_types)
        self.assertIn("tool_result", event_types)
        self.assertIn("done", event_types)

        tool_call_event = next(e for e in events if e["type"] == "tool_call")
        self.assertEqual(tool_call_event["tool"], "get_stock_quote")
        self.assertEqual(tool_call_event["args"], {"symbol": "NVDA"})

        tool_result_event = next(e for e in events if e["type"] == "tool_result")
        self.assertEqual(tool_result_event["data"], {"symbol": "NVDA", "price": 120.50})

        full_text = "".join(e["content"] for e in events if e["type"] == "text_chunk")
        self.assertIn("NVDA Price: $120.50", full_text)

    def test_mongodb_mcp_works_with_deepseek(self):
        """MongoDB MCP tools (e.g. mongo_find) execute and integrate with DeepSeek responses."""
        tool = SimpleNamespace(
            name="mongo_find",
            description="Find documents in MongoDB collection",
            inputSchema={
                "type": "object",
                "properties": {
                    "database": {"type": "string"},
                    "collection": {"type": "string"},
                    "query": {"type": "object"},
                    "limit": {"type": "integer"},
                },
                "required": ["collection"],
            }
        )

        mock_mongo_docs = [
            {"_id": "1", "name": "Venta Q1", "monto": 50000},
            {"_id": "2", "name": "Venta Q2", "monto": 75000},
        ]

        round1_lines = make_tool_call_chunks(
            "call_mongo_001",
            "mongo_find",
            {"collection": "ventas", "limit": 10},
        )
        round2_lines = [
            make_text_chunk("```html\n<table><tr><td>Venta Q1</td><td>50000</td></tr></table>\n```", finish_reason="stop"),
            "data: [DONE]",
        ]

        fake_http = FakeAsyncClient([
            FakeStreamResponse(round1_lines, status_code=200),
            FakeStreamResponse(round2_lines, status_code=200),
        ])

        with patch.object(main, "MCP_ENABLED", True), \
             patch.object(main.mcp_client, "list_tools", new_callable=AsyncMock, return_value=[tool]), \
             patch.object(main.mcp_client, "call_tool", new_callable=AsyncMock, return_value={"documents": mock_mongo_docs, "count": 2}) as mock_call, \
             patch("httpx.AsyncClient", return_value=fake_http):
            res = self.client.post("/api/generate", json={"message": "Muestra las ventas desde MongoDB", "lang": "es"})

        self.assertEqual(res.status_code, 200)
        events = self.parse_sse(res.text)

        mock_call.assert_awaited_once_with("mongo_find", {"collection": "ventas", "limit": 10})
        tool_call_event = next(e for e in events if e["type"] == "tool_call")
        self.assertEqual(tool_call_event["tool"], "mongo_find")

        tool_result_event = next(e for e in events if e["type"] == "tool_result")
        self.assertEqual(tool_result_event["data"]["count"], 2)

        self.assertEqual(events[-1]["type"], "done")
        full_text = "".join(e["content"] for e in events if e["type"] == "text_chunk")
        self.assertIn("Venta Q1", full_text)

    def test_spanish_error_messages(self):
        """Clear Spanish error messages for missing key, auth failed, quota, model, service error."""
        # 1. Missing key
        with patch.object(main, "DEEPSEEK_API_KEY", ""):
            res = self.client.post("/api/generate", json={"message": "Hola", "lang": "es", "provider": "deepseek"})
            self.assertEqual(res.status_code, 503)
            self.assertIn("clave de api ausente", res.json()["detail"].lower())

        # 2. Auth failed (401)
        fake_401 = FakeAsyncClient([FakeStreamResponse([], status_code=401)])
        with patch("httpx.AsyncClient", return_value=fake_401):
            res = self.client.post("/api/generate", json={"message": "Hola", "lang": "es"})
            events = self.parse_sse(res.text)
            self.assertEqual(events[-1]["type"], "error")
            self.assertIn("autenticación fallida", events[-1]["content"].lower())

        # 3. Quota exhausted (429)
        fake_429 = FakeAsyncClient([FakeStreamResponse([], status_code=429)])
        with patch("httpx.AsyncClient", return_value=fake_429):
            res = self.client.post("/api/generate", json={"message": "Hola", "lang": "es"})
            events = self.parse_sse(res.text)
            self.assertEqual(events[-1]["type"], "error")
            self.assertIn("cuota agotada", events[-1]["content"].lower())

        # 4. Model not available (404)
        fake_404 = FakeAsyncClient([FakeStreamResponse([], status_code=404)])
        with patch("httpx.AsyncClient", return_value=fake_404):
            res = self.client.post("/api/generate", json={"message": "Hola", "lang": "es"})
            events = self.parse_sse(res.text)
            self.assertEqual(events[-1]["type"], "error")
            self.assertIn("modelo no disponible", events[-1]["content"].lower())

        # 5. Service temporary error (503)
        fake_503 = FakeAsyncClient([FakeStreamResponse([], status_code=503)])
        with patch("httpx.AsyncClient", return_value=fake_503):
            res = self.client.post("/api/generate", json={"message": "Hola", "lang": "es"})
            events = self.parse_sse(res.text)
            self.assertEqual(events[-1]["type"], "error")
            self.assertIn("error temporal del servicio", events[-1]["content"].lower())

    def test_provider_selection_modes(self):
        """LLM_PROVIDER and request provider override work properly."""
        # 1. Provider = gemini
        with patch.object(main, "LLM_PROVIDER", "gemini"), \
             patch.object(main, "GEMINI_API_KEYS", []):
            res = self.client.post("/api/generate", json={"message": "Hola"})
            self.assertEqual(res.status_code, 503)
            self.assertIn("gemini", res.json()["detail"].lower())

        # 2. Request body override to secondary (groq; deepseek aceptado como alias legacy)
        with patch.object(main, "LLM_PROVIDER", "gemini"), \
             patch.object(main, "DEEPSEEK_API_KEY", ""), \
             patch.object(main, "GROQ_API_KEY", ""):
            res = self.client.post("/api/generate", json={"message": "Hola", "provider": "deepseek"})
            self.assertEqual(res.status_code, 503)
            self.assertIn("groq", res.json()["detail"].lower())
            res2 = self.client.post("/api/generate", json={"message": "Hola", "provider": "groq"})
            self.assertEqual(res2.status_code, 503)
            self.assertIn("groq", res2.json()["detail"].lower())

    def test_groq_is_secondary_provider(self):
        """Groq responde como secundario con endpoint OpenAI-compatible."""
        html_code = "```html\n<div>Groq Financial Dashboard</div>\n```"
        lines = [
            make_text_chunk("Generando interfaz... "),
            make_text_chunk(html_code, finish_reason="stop"),
            "data: [DONE]",
        ]
        fake_client = FakeAsyncClient([FakeStreamResponse(lines, status_code=200)])

        with patch.object(main, "GROQ_API_KEY", self.groq_key), \
             patch.object(main, "GROQ_MODEL", "openai/gpt-oss-120b"), \
             patch.object(main, "GROQ_BASE_URL", "https://api.groq.com/openai/v1"), \
             patch.object(main, "LLM_PROVIDER", "groq"), \
             patch("httpx.AsyncClient", return_value=fake_client):
            res = self.client.post("/api/generate", json={"message": "Crea un dashboard", "lang": "es", "provider": "groq"})

        self.assertEqual(res.status_code, 200)
        events = self.parse_sse(res.text)
        self.assertEqual(events[-1]["type"], "done")
        full_text = "".join(e["content"] for e in events if e["type"] == "text_chunk")
        self.assertIn("Groq Financial Dashboard", full_text)
        call = fake_client.calls[0]
        self.assertEqual(call["url"], "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(call["headers"]["Authorization"], f"Bearer {self.groq_key}")
        self.assertEqual(call["json"]["model"], "openai/gpt-oss-120b")


if __name__ == "__main__":
    unittest.main()
