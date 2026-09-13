import asyncio
import json
import os
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from bson import Binary, Code, Decimal128, ObjectId, Regex, Timestamp
from fastapi.testclient import TestClient
from google.genai import types
from pymongo.errors import ConfigurationError, OperationFailure, ServerSelectionTimeoutError

import main
import mcp_mongodb
from database.mongodb import (
    ALLOWED_STAGES, MAX_RESULT_BYTES, MongoDB, MongoDBError,
    validate_collection, validate_database, validate_limit, validate_pipeline,
    validate_projection, validate_query, validate_sort,
)
from database.serializers import to_jsonable

TOOL_NAMES = {
    "mongo_ping", "mongo_list_databases", "mongo_list_collections", "mongo_get_schema",
    "mongo_find", "mongo_count", "mongo_aggregate",
}


def cursor_for(rows):
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.__iter__.side_effect = lambda: iter(rows)
    return cursor


class SerializationTests(unittest.TestCase):
    def test_nested_bson_and_simple_values(self):
        oid = ObjectId()
        value = {"_id": oid, "nested": [{"amount": Decimal128("123.40"),
                 "date": datetime(2026, 1, 2), "flag": True}], "null": None, "n": 7}
        result = to_jsonable(value)
        self.assertEqual(result["_id"], str(oid))
        self.assertEqual(result["nested"][0]["amount"], "123.40")
        self.assertEqual(result["nested"][0]["date"], "2026-01-02T00:00:00+00:00")
        self.assertEqual(json.loads(json.dumps(result)), result)
        self.assertIsInstance(value["_id"], ObjectId)

    def test_other_bson_and_nonfinite_numbers_are_json_safe(self):
        values = [Binary(b"hello"), Regex("a", "i"), Timestamp(1, 2), float("nan"),
                  float("inf"), float("-inf"), datetime.now(timezone.utc)]
        json.dumps(to_jsonable(values), allow_nan=False)


class ValidationTests(unittest.TestCase):
    def test_database_defaults_and_override(self):
        with patch.dict(os.environ, {"MONGODB_DATABASE": "finance"}):
            self.assertEqual(validate_database(None), "finance")
            self.assertEqual(validate_database("analytics"), "analytics")
        with patch.dict(os.environ, {"MONGODB_DATABASE": ""}):
            with self.assertRaisesRegex(MongoDBError, "database was not specified"):
                validate_database(None)

    def test_invalid_names(self):
        for name in ("", "a.b", "a/b", "a\\b", "a b", "a$", "a\x00b", "é" * 32, 1, False, {}):
            with self.subTest(database=repr(name)), self.assertRaises(MongoDBError):
                validate_database(name)
        for name in ("", None, 1, "a$", "a\x00b", ".a", "a.", "a..b", " x", "x" * 121):
            with self.subTest(collection=repr(name)), self.assertRaises(MongoDBError):
                validate_collection(name)
        self.assertEqual(validate_collection("transactions.2026"), "transactions.2026")

    def test_limits_reject_unbounded_negative_coerced_and_large_values(self):
        self.assertEqual(validate_limit(), 20)
        for value in (1, 20, 100):
            self.assertEqual(validate_limit(value), value)
        for value in (0, -1, 101, 1000000, True, False, "20", 20.0, None):
            with self.subTest(value=value), self.assertRaises(MongoDBError):
                validate_limit(value)

    def test_safe_filters_and_extended_json(self):
        oid = ObjectId()
        query = {"$and": [{"amount": {"$gte": 10}}, {"status": {"$in": ["paid", "pending"]}}],
                 "_id": {"$oid": str(oid)}, "date": {"$gte": {"$date": "2026-01-01T00:00:00Z"}},
                 "price": {"$numberDecimal": "1.25"}}
        validated = validate_query(query)
        self.assertEqual(validated["_id"], oid)
        self.assertIsInstance(validated["date"]["$gte"], datetime)
        self.assertEqual(validated["price"], Decimal128("1.25"))
        self.assertIsInstance(query["_id"], dict)
        self.assertEqual(validate_query(), {})

    def test_query_types_size_depth_and_invalid_literals(self):
        deep = {}
        for _ in range(25):
            deep = {"nested": deep}
        for value in ([], "{}", False, {"bad": float("nan")}, {"bad": 2**64},
                      {"bad": Code("return true")}, {1: "bad"}, {"x": "x" * 66000}, deep,
                      {"x": {"$oid": None}}, {"x": {"$oid": "invalid"}},
                      {"x": {"$date": "yesterday"}}, {"x": {"$numberDecimal": []}}):
            with self.subTest(kind=type(value).__name__), self.assertRaises(MongoDBError):
                validate_query(value)

    def test_dangerous_operators_are_blocked_recursively(self):
        for operator in ("$where", "$function", "$accumulator", "$out", "$merge", "$eval", "$code"):
            value = {"$and": [{"nested": [{operator: "not executed"}]}]}
            with self.subTest(operator=operator), self.assertRaises(MongoDBError):
                validate_query(value)
            with self.subTest(pipeline_operator=operator), self.assertRaises(MongoDBError):
                validate_pipeline([{"$project": {"nested": [value]}}])

    def test_projection_and_sort(self):
        self.assertEqual(validate_projection({"amount": 1, "_id": 0}), {"amount": 1, "_id": 0})
        self.assertEqual(validate_sort({"amount": -1, "date": 1}), [("amount", -1), ("date", 1)])
        for projection in ([], {"x": 1, "y": 0}, {"x": {"$function": {}}}, {"x": 2}):
            with self.assertRaises(MongoDBError):
                validate_projection(projection)
        for sort in ([], {}, {"x": True}, {"x": 0}, {"x": "desc"}, {"$where": 1}):
            with self.assertRaises(MongoDBError):
                validate_sort(sort)

    def test_pipeline_allowlist_and_terminal_cap_without_mutating_input(self):
        pipeline = [{"$match": {"status": "paid"}}, {"$unwind": "$items"},
                    {"$group": {"_id": "$category", "total": {"$sum": "$amount"}}},
                    {"$sort": {"total": -1}}, {"$limit": 5}, {"$project": {"total": 1}},
                    {"$addFields": {"currency": "USD"}}, {"$set": {"label": "total"}},
                    {"$skip": 0}, {"$count": "categories"}]
        original = json.dumps(pipeline)
        self.assertEqual({next(iter(stage)) for stage in pipeline}, ALLOWED_STAGES)
        self.assertEqual(validate_pipeline(pipeline)[-1], {"$limit": 100})
        self.assertEqual(json.dumps(pipeline), original)
        self.assertEqual(validate_pipeline([]), [{"$limit": 100}])

    def test_unsafe_and_malformed_pipelines(self):
        for stage in ("$out", "$merge"):
            with self.assertRaisesRegex(MongoDBError, "read-only"):
                validate_pipeline([{stage: "archive"}])
        invalid = [None, {}, "[]", [None], [{}], [{"$match": {}, "$out": "x"}],
                   [{"$lookup": {"from": "x"}}], [{"$currentOp": {}}], [{"$changeStream": {}}],
                   [{"$facet": {"x": [{"$merge": "x"}]}}], [{"$match": []}], [{"$group": {}}],
                   [{"$limit": 0}], [{"$limit": True}], [{"$skip": -1}], [{"$skip": 1000001}],
                   [{"$count": "$bad"}], [{"$count": "bad.path"}], [{"$unwind": "items"}],
                   [{"$unwind": {"path": "$items", "preserveNullAndEmptyArrays": 1}}],
                   [{"$sort": {"x": 2}}], [{"$match": {}}] * 21]
        for pipeline in invalid:
            with self.subTest(pipeline=pipeline), self.assertRaises(MongoDBError):
                validate_pipeline(pipeline)


class MongoDBAccessTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(os.environ, {"MONGODB_URI": "mongodb://localhost:27017", "MONGODB_DATABASE": "finance"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        # No write/administrative APIs exist on these mocks: accidental writes fail.
        self.collection = MagicMock(spec_set=["find", "count_documents", "aggregate"])
        self.database = MagicMock(spec_set=["__getitem__", "list_collections"])
        self.database.__getitem__.return_value = self.collection
        self.client = MagicMock(spec_set=["__getitem__", "admin", "list_databases", "close"])
        self.client.__getitem__.return_value = self.database
        self.factory = patch("database.mongodb.MongoClient", return_value=self.client)
        self.make_client = self.factory.start()
        self.addCleanup(self.factory.stop)
        self.db = MongoDB()
        self.addCleanup(self.db.close)

    def test_lazy_connection_reuse_timeouts_and_close(self):
        self.make_client.assert_not_called()
        self.assertTrue(self.db.ping()["ok"])
        self.db.ping()
        self.make_client.assert_called_once()
        options = self.make_client.call_args.kwargs
        self.assertFalse(options["connect"])
        self.assertEqual(options["serverSelectionTimeoutMS"], 5000)
        self.assertEqual(options["timeoutMS"], 10000)
        self.client.admin.command.assert_called_with("ping", maxTimeMS=5000)
        self.db.close()
        self.client.close.assert_called_once()

    def test_missing_configuration_and_safe_driver_errors(self):
        with patch.dict(os.environ, {"MONGODB_URI": ""}):
            with self.assertRaisesRegex(MongoDBError, "MONGODB_URI is not configured"):
                self.db.ping()
        self.make_client.assert_not_called()
        self.make_client.side_effect = ConfigurationError("mongodb://user:super-secret@host")
        with self.assertRaises(MongoDBError) as caught:
            self.db.ping()
        self.assertNotIn("super-secret", str(caught.exception))
        self.make_client.side_effect = None
        for error in (OperationFailure("super-secret", code=13), OperationFailure("super-secret", code=18),
                      OperationFailure("super-secret", code=2), ServerSelectionTimeoutError("super-secret")):
            self.client.admin.command.side_effect = error
            with self.assertRaises(MongoDBError) as caught:
                self.db.ping()
            self.assertNotIn("super-secret", str(caught.exception))

    def test_lists_use_authorized_metadata_and_explicit_database(self):
        self.client.list_databases.return_value = cursor_for([{"name": "finance"}])
        self.database.list_collections.return_value = cursor_for([{"name": "transactions"}])
        self.assertEqual(self.db.list_databases()["databases"], ["finance"])
        self.assertEqual(self.db.list_collections("analytics")["collections"], ["transactions"])
        self.client.__getitem__.assert_called_with("analytics")
        self.assertTrue(self.client.list_databases.call_args.kwargs["authorizedDatabases"])
        self.assertTrue(self.database.list_collections.call_args.kwargs["authorizedCollections"])

    def test_find_count_and_bson_serialization(self):
        oid = ObjectId()
        cursor = cursor_for([{"_id": oid, "amount": Decimal128("3.50")}])
        self.collection.find.return_value = cursor
        self.collection.count_documents.return_value = 83
        result = self.db.find("transactions", query={"_id": {"$oid": str(oid)}},
                              projection={"amount": 1}, sort={"amount": -1}, limit=5)
        self.assertEqual(result["documents"][0]["amount"], "3.50")
        self.collection.find.assert_called_once_with({"_id": oid}, projection={"amount": 1},
            sort=[("amount", -1)], limit=5, max_time_ms=5000, batch_size=5)
        self.assertEqual(self.db.count("transactions", query={"status": "paid"})["count"], 83)
        self.collection.count_documents.assert_called_once_with({"status": "paid"}, maxTimeMS=5000)
        cursor.__exit__.assert_called_once()

    def test_schema_is_bounded_and_infers_nested_mixed_types(self):
        rows = [{"_id": ObjectId(), "amount": Decimal128("1"), "customer": {"name": "A"},
                 "items": [{"qty": 1}], "optional": None}, {"amount": 2.0}] * 30
        self.collection.find.return_value = cursor_for(rows)
        result = self.db.get_schema("transactions")
        self.assertEqual(result["sample_size"], 50)
        fields = {row["field"]: row["types"] for row in result["fields"]}
        self.assertEqual(fields["amount"], ["Decimal128", "float"])
        self.assertEqual(fields["items[].qty"], ["int"])
        self.assertEqual(fields["optional"], ["null"])
        self.assertNotIn("documents", result)
        self.collection.find.return_value = cursor_for([])
        self.assertEqual(self.db.get_schema("empty")["fields"], [])

    def test_aggregation_caps_results_and_disallows_disk_use(self):
        self.collection.aggregate.return_value = cursor_for([{"total": 1}] * 200)
        pipeline = [{"$group": {"_id": "$category", "total": {"$sum": "$amount"}}}]
        result = self.db.aggregate("transactions", pipeline)
        self.assertEqual(result["returned"], 100)
        self.assertTrue(result["limit_reached"])
        self.collection.aggregate.assert_called_once_with(pipeline + [{"$limit": 100}],
            maxTimeMS=5000, allowDiskUse=False, batchSize=100)
        self.assertEqual(len(pipeline), 1)

    def test_validation_precedes_connection_and_queries(self):
        for operation, kwargs in ((self.db.find, {"limit": 0}),
                                  (self.db.count, {"query": {"$where": "evil"}}),
                                  (self.db.aggregate, {"pipeline": [{"$out": "x"}]})):
            with self.assertRaises(MongoDBError):
                operation("transactions", **kwargs)
        self.make_client.assert_not_called()

    def test_oversized_documents_are_rejected_and_cursor_closed(self):
        cursor = cursor_for([{"large": "x" * (MAX_RESULT_BYTES + 1)}])
        self.collection.find.return_value = cursor
        with self.assertRaisesRegex(MongoDBError, "1 MiB"):
            self.db.find("transactions")
        cursor.__exit__.assert_called_once()

    def test_all_seven_mcp_wrappers_use_the_access_layer(self):
        self.collection.find.return_value = cursor_for([{"amount": 5}])
        self.collection.aggregate.return_value = cursor_for([{"total": 5}])
        self.collection.count_documents.return_value = 1
        self.client.list_databases.return_value = cursor_for([{"name": "finance"}])
        self.database.list_collections.return_value = cursor_for([{"name": "transactions"}])
        with patch.object(mcp_mongodb, "mongodb", self.db):
            for name in TOOL_NAMES:
                kwargs = {"collection": "transactions"} if name in {"mongo_find", "mongo_count", "mongo_aggregate", "mongo_get_schema"} else {}
                if name == "mongo_aggregate":
                    kwargs["pipeline"] = [{"$group": {"_id": None, "total": {"$sum": "$amount"}}}]
                with self.subTest(tool=name):
                    payload = json.loads(getattr(mcp_mongodb, name)(**kwargs))
                    self.assertTrue(payload["ok"], payload)
                    self.assertEqual(payload["source"], "live-mongodb")
            result = json.loads(mcp_mongodb.mongo_find("transactions", query={"$where": "evil"}))
            self.assertFalse(result["ok"])
            self.assertIn("$where", result["error"])
            self.client.admin.command.side_effect = RuntimeError("mongodb://user:secret@host")
            self.assertNotIn("secret", mcp_mongodb.mongo_ping())


class MCPMongoIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_stdio_discovery_without_uri_and_existing_servers(self):
        with patch.dict(os.environ, {"MONGODB_URI": "", "MONGODB_DATABASE": "finance"}):
            client = main.MCPFinancialClient()
            tools = await client.list_tools()
            self.assertTrue(TOOL_NAMES <= {tool.name for tool in tools})
            self.assertIn("get_live_quote", {tool.name for tool in tools})
            self.assertIn("get_ecb_rates", {tool.name for tool in tools})
            declarations = main.build_gemini_tools(tools)[0].function_declarations
            self.assertTrue(TOOL_NAMES <= {tool.name for tool in declarations})
            for tool in tools:
                if tool.name in TOOL_NAMES:
                    annotations = tool.annotations.model_dump(by_alias=True)
                    self.assertTrue(annotations["readOnlyHint"])
                    self.assertFalse(annotations["destructiveHint"])
            result = await client.call_tool("mongo_ping", {})
            self.assertFalse(result["ok"])
            self.assertIn("MONGODB_URI is not configured", result["error"])
            result = await client.call_tool("mongo_aggregate", {"collection": "x", "pipeline": [{"$out": "x"}]})
            self.assertIn("read-only", result["error"])
            demo = await client.call_tool("get_stock_quote", {"symbol": "AAPL"})
            self.assertEqual(demo["symbol"], "AAPL")

    async def test_environment_forwarding_and_no_frontend_credentials(self):
        secret = "invalid-uri-with-private-credentials"
        servers = [server for server in main.MCP_SERVERS if server["name"] == "mongodb"]
        with patch.dict(os.environ, {"MONGODB_URI": secret, "MONGODB_DATABASE": "finance"}), \
                patch.object(main, "MCP_ENABLED", True), patch.object(main, "mcp_client", main.MCPFinancialClient(servers)):
            result = await main.mcp_client.call_tool("mongo_ping", {})
            self.assertIn("Invalid MONGODB_URI", result["error"])
            with TestClient(main.app) as web:
                for url in ("/", "/health", "/api/tools", "/static/app.js"):
                    response = web.get(url)
                    self.assertEqual(response.status_code, 200)
                    self.assertNotIn(secret, response.text)
                response = web.post("/api/tool-call", json={"tool": "mongo_ping"})
                self.assertFalse(response.json()["data"]["ok"])
                self.assertNotIn(secret, response.text)

    async def test_gemini_receives_mongodb_tools_and_actionable_stdio_result(self):
        class FakeGemini:
            def __init__(self):
                self.aio = self
                self.models = self
                self.calls = []

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def generate_content_stream(self, **kwargs):
                self.calls.append({**kwargs, "contents": list(kwargs["contents"])})
                part = (types.Part(function_call=types.FunctionCall(name="mongo_ping", args={}))
                        if len(self.calls) == 1 else types.Part(text="Configure MONGODB_URI on the server."))

                async def stream():
                    yield types.GenerateContentResponse(candidates=[types.Candidate(
                        content=types.Content(role="model", parts=[part]), finish_reason=types.FinishReason.STOP)])
                return stream()

        fake = FakeGemini()
        servers = [server for server in main.MCP_SERVERS if server["name"] == "mongodb"]
        with patch.dict(os.environ, {"MONGODB_URI": ""}), patch.object(main, "MCP_ENABLED", True), \
                patch.object(main, "mcp_client", main.MCPFinancialClient(servers)), \
                patch.object(main.genai, "Client", return_value=fake):
            events = [json.loads(frame[6:]) async for frame in main.run_agent_stream("Ping MongoDB")]
        self.assertEqual(events[-1]["type"], "done")
        self.assertEqual({tool.name for tool in fake.calls[0]["config"].tools[0].function_declarations}, TOOL_NAMES)
        response = fake.calls[1]["contents"][2].parts[0].function_response.response["result"]
        self.assertFalse(response["ok"])
        self.assertIn("MONGODB_URI is not configured", response["error"])


@unittest.skipUnless(os.getenv("MONGODB_TEST_URI") and os.getenv("MONGODB_TEST_DATABASE")
                     and os.getenv("MONGODB_TEST_COLLECTION"), "Live MongoDB credentials/collection not configured")
class LiveMongoDBTests(unittest.TestCase):
    def test_read_only_connection_and_collection(self):
        with patch.dict(os.environ, {"MONGODB_URI": os.environ["MONGODB_TEST_URI"],
                                    "MONGODB_DATABASE": os.environ["MONGODB_TEST_DATABASE"]}):
            db = MongoDB()
            self.addCleanup(db.close)
            collection = os.environ["MONGODB_TEST_COLLECTION"]
            self.assertTrue(db.ping()["ok"])
            self.assertIsInstance(db.list_databases()["databases"], list)
            self.assertIsInstance(db.list_collections()["collections"], list)
            self.assertLessEqual(db.get_schema(collection)["sample_size"], 50)
            self.assertLessEqual(db.find(collection, limit=1)["returned"], 1)
            self.assertIsInstance(db.count(collection)["count"], int)
            self.assertLessEqual(db.aggregate(collection, [{"$limit": 1}])["returned"], 1)


if __name__ == "__main__":
    unittest.main()
