"""Capa realtime (Socket.io) + persistencia (mongo_store) de la rama unificada.

Herméticos: no dependen de red ni del .env local; el estado global de
mongo_store se congela y restaura en cada test.
"""

import asyncio
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
import mongo_store
import socket_events


def _snapshot():
    return {
        "MONGODB_URI": mongo_store.MONGODB_URI,
        "client": mongo_store.client,
        "db": mongo_store.db,
        "MONGODB_AVAILABLE": mongo_store.MONGODB_AVAILABLE,
    }


def _restore(snap):
    mongo_store.MONGODB_URI = snap["MONGODB_URI"]
    mongo_store.client = snap["client"]
    mongo_store.db = snap["db"]
    mongo_store.MONGODB_AVAILABLE = snap["MONGODB_AVAILABLE"]


class RealtimeMongoTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self._snap = _snapshot()
        self.addCleanup(_restore, self._snap)

    def test_health_exposes_realtime_flags_without_secrets(self):
        body = self.client.get("/health").json()
        self.assertTrue(body["ws_live"])
        self.assertIsInstance(body["socketio_enabled"], bool)
        self.assertIsInstance(body["mongodb_enabled"], bool)
        self.assertNotIn("MONGODB_URI", str(body))

    def test_socket_app_wraps_fastapi(self):
        self.assertTrue(main.SOCKETIO_AVAILABLE)
        self.assertIsNotNone(main.socket_app)
        result = self.client.get("/")
        self.assertEqual(result.status_code, 200)

    def test_socket_events_module(self):
        self.assertEqual(socket_events.get_users_count(), 0)
        for name in (
            "emit_generation_start", "emit_tool_call", "emit_tool_result",
            "emit_a2ui_update", "emit_price_update", "emit_generation_complete",
            "emit_generation_error", "broadcast_data_refresh",
        ):
            self.assertTrue(callable(getattr(socket_events, name)), name)

    def test_connect_without_uri_falls_back_gracefully(self):
        mongo_store.MONGODB_URI = ""
        mongo_store.client = None
        mongo_store.db = None
        mongo_store.MONGODB_AVAILABLE = False
        asyncio.run(mongo_store.connect_db())
        self.assertFalse(mongo_store.MONGODB_AVAILABLE)
        self.assertIsNone(mongo_store.get_db())
        self.assertIsNone(mongo_store.users_collection())
        self.assertIsNone(mongo_store.datasets_collection())
        asyncio.run(mongo_store.close_db())

    def test_connect_failure_falls_back_gracefully(self):
        mongo_store.MONGODB_URI = "mongodb://unreachable:27017"
        mongo_store.client = None
        mongo_store.db = None
        mongo_store.MONGODB_AVAILABLE = False

        class Boom:
            def __init__(self, *args, **kwargs):
                raise RuntimeError("no mongo here")

        with patch.object(mongo_store, "AsyncIOMotorClient", Boom):
            asyncio.run(mongo_store.connect_db())
        self.assertFalse(mongo_store.MONGODB_AVAILABLE)
        self.assertIsNone(mongo_store.client)
        self.assertIsNone(mongo_store.db)


if __name__ == "__main__":
    unittest.main()
