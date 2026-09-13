"""Live channel tests: /ws/live ticks, threshold alerts, prefs sync, agent push."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

import main


def quote_tool(name):
    return SimpleNamespace(name=name, description=name)


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        main._save_users({})
        main.live.conns.clear()
        main.live.last_agent.clear()
        if main.live._ticker_task is not None:
            main.live._ticker_task.cancel()
            main.live._ticker_task = None
        self.mcp = patch.object(main, "MCP_ENABLED", True)
        self.mcp.start()
        self.addCleanup(self.mcp.stop)

    def tearDown(self):
        main.live.conns.clear()
        main.live.last_agent.clear()
        if main.live._ticker_task is not None:
            main.live._ticker_task.cancel()
            main.live._ticker_task = None
        main._save_users({})

    def login(self, user="liv"):
        self.client.post("/api/auth/register", json={"user": user, "password": "secret1"})
        return self.client.post("/api/auth/login", json={"user": user, "password": "secret1"}).json()

    def test_hello_guest(self):
        with self.client.websocket_connect("/ws/live") as ws:
            hello = ws.receive_json()
        self.assertEqual(hello["type"], "hello")
        self.assertIn("conn", hello)
        self.assertTrue(hello["live"])
        self.assertEqual(hello["tick_seconds"], main.LIVE_TICK_SECONDS)

    def test_subscribe_and_tick(self):
        tools = [quote_tool("get_live_quote")]
        prices = {"AAPL": {"symbol": "AAPL", "price": 150.0, "change_percent": 1.2}}
        with patch.object(main.mcp_client, "list_tools", new_callable=AsyncMock, return_value=tools), \
                patch.object(main.mcp_client, "call_tool", new_callable=AsyncMock,
                             side_effect=lambda name, args: prices[args["symbol"]]):
            with self.client.websocket_connect("/ws/live") as ws:
                ws.receive_json()  # hello
                ws.send_json({"op": "subscribe", "symbols": ["aapl"], "watches": {}})
                sub = ws.receive_json()
                self.assertEqual(sub["type"], "subscribed")
                self.assertEqual(sub["symbols"], ["AAPL"])
                import asyncio
                asyncio.run(main.live.poll_once())
                tick = ws.receive_json()
        self.assertEqual(tick["type"], "tick")
        self.assertEqual(tick["symbol"], "AAPL")
        self.assertEqual(tick["price"], 150.0)

    def test_alert_on_threshold_cross(self):
        tools = [quote_tool("get_live_quote")]
        state = {"price": 190.0}

        async def fake_call(name, args):
            return {"symbol": "AAPL", "price": state["price"], "change_percent": 0.5}

        with patch.object(main.mcp_client, "list_tools", new_callable=AsyncMock, return_value=tools), \
                patch.object(main.mcp_client, "call_tool", new_callable=AsyncMock, side_effect=fake_call):
            import asyncio
            with self.client.websocket_connect("/ws/live") as ws:
                ws.receive_json()  # hello
                ws.send_json({"op": "subscribe", "symbols": ["AAPL"],
                              "watches": {"AAPL": {"above": 200, "below": None}}})
                ws.receive_json()  # subscribed
                asyncio.run(main.live.poll_once())  # seeds 190, no alert
                first = ws.receive_json()
                self.assertEqual(first["type"], "tick")
                state["price"] = 210.0
                asyncio.run(main.live.poll_once())  # crosses 200 -> alert
                second = ws.receive_json()
                alert = ws.receive_json()
        self.assertEqual(second["type"], "tick")
        self.assertEqual(alert["type"], "alert")
        self.assertEqual(alert["condition"], "above")
        self.assertEqual(alert["threshold"], 200)

    def test_no_quote_tool_status(self):
        with patch.object(main.mcp_client, "list_tools", new_callable=AsyncMock, return_value=[]):
            import asyncio
            with self.client.websocket_connect("/ws/live") as ws:
                ws.receive_json()  # hello
                ws.send_json({"op": "subscribe", "symbols": ["AAPL"]})
                ws.receive_json()  # subscribed
                asyncio.run(main.live.poll_once())
                status = ws.receive_json()
        self.assertEqual(status["type"], "status")
        self.assertEqual(status["code"], "no_quote_tool")

    def test_prefs_require_auth(self):
        self.assertEqual(self.client.get("/api/prefs").status_code, 401)
        self.assertEqual(self.client.put("/api/prefs", json={"model": ""}).status_code, 401)

    def test_prefs_roundtrip_and_validation(self):
        login = self.login()
        headers = {"Authorization": "Bearer " + login["token"]}
        self.assertEqual(self.client.get("/api/prefs", headers=headers).json(),
                         {"model": "", "dataset_id": None, "lang": "es", "watches": []})
        with patch.object(main, "GEMINI_MODELS", ["model-a", "model-b"]):
            saved = self.client.put("/api/prefs", headers=headers, json={
                "model": "model-a", "lang": "en",
                "watches": [{"symbol": "aapl", "above": 200, "below": None}]},
            ).json()
            self.assertEqual(saved["model"], "model-a")
            self.assertEqual(saved["lang"], "en")
            self.assertEqual(saved["watches"], [{"symbol": "AAPL", "above": 200.0, "below": None}])
            bad = self.client.put("/api/prefs", headers=headers, json={"model": "nope"})
            self.assertEqual(bad.status_code, 422)

    def test_agent_progress_reaches_other_socket(self):
        login = self.login()
        token = login["token"]
        import asyncio
        with self.client.websocket_connect(f"/ws/live?token={token}") as ws:
            hello = ws.receive_json()
            self.assertIn("conn", hello)
            asyncio.run(main.live.notify_agent(token, "status", "Connecting to Gemini..."))
            msg = ws.receive_json()
        self.assertEqual(msg["type"], "agent")
        self.assertEqual(msg["kind"], "status")

    def test_sync_broadcast_to_same_user(self):
        login = self.login()
        token = login["token"]
        headers = {"Authorization": "Bearer " + token}
        with self.client.websocket_connect(f"/ws/live?token={token}") as ws:
            hello = ws.receive_json()
            with patch.object(main, "GEMINI_MODELS", ["model-a"]):
                res = self.client.put("/api/prefs", headers=headers, json={
                    "model": "model-a", "via": hello["conn"]})
            self.assertEqual(res.status_code, 200)
            # excluded conn (sender) gets nothing; open a second socket instead
        with self.client.websocket_connect(f"/ws/live?token={token}") as ws2:
            ws2.receive_json()  # hello
            with patch.object(main, "GEMINI_MODELS", ["model-a"]):
                self.client.put("/api/prefs", headers=headers, json={"model": "model-a"})
            sync = ws2.receive_json()
        self.assertEqual(sync["type"], "sync")
        self.assertEqual(sync["prefs"]["model"], "model-a")


if __name__ == "__main__":
    unittest.main()
