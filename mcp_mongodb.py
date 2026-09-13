"""Read-only MongoDB tools using the same stdio MCP API as the bundled servers."""

import atexit
import json
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from pydantic import Field

from database.mongodb import MAX_RESULT_BYTES, MongoDB, MongoDBError
from database.serializers import to_jsonable

try:
    from mcp.server.fastmcp import FastMCP
    from mcp.types import ToolAnnotations
    server = FastMCP("glintmesh-mongodb")
except ModuleNotFoundError:
    from mcp.server.mcpserver import MCPServer
    from mcp_types import ToolAnnotations
    server = MCPServer("glintmesh-mongodb")

load_dotenv(Path(__file__).resolve().parent / ".env")
mongodb = MongoDB()  # No connection, URI parsing, or ping during import/discovery.
atexit.register(mongodb.close)
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True)
FindLimit = Annotated[int, Field(strict=True, ge=1, le=100)]


def _result(operation, **kwargs):
    try:
        payload = {"ok": True, "source": "live-mongodb", **operation(**kwargs)}
        text = json.dumps(to_jsonable(payload), ensure_ascii=True, allow_nan=False)
        if len(text.encode("utf-8")) > MAX_RESULT_BYTES:
            raise MongoDBError("MongoDB results exceed 1 MiB. Select fewer fields or a smaller sample.")
        return text
    except MongoDBError as exc:
        # Application-level errors stay visible to Gemini: the existing adapter
        # intentionally hides SDK exceptions and MCP protocol errors.
        return json.dumps({"ok": False, "error": str(exc)})
    except Exception:
        # Never log or forward raw driver/serialization errors or configuration.
        return json.dumps({"ok": False, "error": "MongoDB could not complete this read. Check the arguments and server configuration."})


@server.tool(annotations=READ_ONLY)
def mongo_ping() -> str:
    """Check MongoDB connectivity. Returns ok=false with a safe error if unconfigured or unavailable."""
    return _result(mongodb.ping)


@server.tool(annotations=READ_ONLY)
def mongo_list_databases() -> str:
    """List up to 100 databases visible to the MongoDB user; truncated indicates more exist. Read-only."""
    return _result(mongodb.list_databases)


@server.tool(annotations=READ_ONLY)
def mongo_list_collections(database: str | None = None) -> str:
    """List up to 100 visible collections. Omit database to use MONGODB_DATABASE. Read-only."""
    return _result(mongodb.list_collections, database=database)


@server.tool(annotations=READ_ONLY)
def mongo_get_schema(collection: str, database: str | None = None) -> str:
    """Infer approximate fields/types from up to 50 documents and 50 elements per array, depth 20.
    Use this before querying an unfamiliar collection. Omit database to use MONGODB_DATABASE.
    MongoDB is schema-less; this sample may miss fields/types. Read-only.
    """
    return _result(mongodb.get_schema, collection=collection, database=database)


@server.tool(annotations=READ_ONLY)
def mongo_find(collection: str, database: str | None = None, query: dict | None = None,
               projection: dict | None = None, sort: dict | None = None, limit: FindLimit = 20) -> str:
    """Read real MongoDB documents; default 20, maximum 100. Never use results when ok=false.
    Omit database to use MONGODB_DATABASE. query is a MongoDB filter object (default {}).
    Supports literals {"$oid":"24 hex characters"}, {"$date":"ISO 8601"},
    {"$numberDecimal":"12.50"}; JavaScript/$where are forbidden recursively.
    projection maps fields to 0/1; sort maps fields to 1/-1. Result budget: 1 MiB.
    """
    return _result(mongodb.find, collection=collection, database=database, query=query,
                   projection=projection, sort=sort, limit=limit)


@server.tool(annotations=READ_ONLY)
def mongo_count(collection: str, database: str | None = None, query: dict | None = None) -> str:
    """Count matching MongoDB documents without fetching them. Read-only.
    Omit database to use MONGODB_DATABASE. query defaults to {}; same literals as mongo_find.
    """
    return _result(mongodb.count, collection=collection, database=database, query=query)


@server.tool(annotations=READ_ONLY)
def mongo_aggregate(collection: str, pipeline: list[dict], database: str | None = None) -> str:
    """Aggregate real MongoDB data for dashboards, read-only, at most 100 results / 1 MiB.
    Omit database to use MONGODB_DATABASE. At most 20 stages, only $match, $group, $sort,
    $limit, $project, $unwind, $count, $addFields, $set, $skip. $set only reshapes results.
    $out/$merge and JavaScript ($where/$function/$accumulator) are forbidden recursively.
    Example: [{"$group":{"_id":"$category","total":{"$sum":"$amount"}}},{"$sort":{"total":-1}}].
    On ok=false, inspect the error and correct the request; never invent successful results.
    """
    return _result(mongodb.aggregate, collection=collection, pipeline=pipeline, database=database)


if __name__ == "__main__":
    try:
        server.run(transport="stdio")
    finally:
        mongodb.close()
