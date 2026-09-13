"""Bounded, read-only MongoDB access. No MCP or web dependencies."""

import json
import math
import os
import warnings
from datetime import datetime
from functools import wraps
from itertools import islice
from threading import Lock

from bson import Decimal128, ObjectId
from pymongo import MongoClient, timeout
from pymongo.errors import OperationFailure, PyMongoError

from database.serializers import to_jsonable

DEFAULT_LIMIT = 20
MAX_RESULTS = 100
SCHEMA_SAMPLE_SIZE = 50
MAX_PIPELINE_STAGES = 20
MAX_INPUT_BYTES = 64 * 1024
MAX_RESULT_BYTES = 1024 * 1024
MAX_DEPTH = 20
MAX_TIME_MS = 5000
ALLOWED_STAGES = frozenset({
    "$match", "$group", "$sort", "$limit", "$project", "$unwind", "$count",
    "$addFields", "$set", "$skip",
})
BLOCKED_OPERATORS = frozenset({
    "$where", "$function", "$accumulator", "$out", "$merge", "$eval",
    "$mapReduce", "$mapreduce", "$code", "$scope",
})


class MongoDBError(ValueError):
    """A safe, actionable message that may be returned to an MCP caller."""


def validate_database(database):
    if database is None:
        database = os.getenv("MONGODB_DATABASE", "").strip()
        if not database:
            raise MongoDBError(
                "MongoDB database was not specified and MONGODB_DATABASE is not configured."
            )
    if (type(database) is not str or not database
            or len(database.encode("utf-8")) > 63
            or any(c in database for c in '/\\. "$*<>:|?')
            or any(ord(c) < 32 for c in database)):
        raise MongoDBError("Invalid MongoDB database name (1-63 UTF-8 bytes, no reserved characters).")
    return database


def validate_collection(collection):
    if (type(collection) is not str or not collection or collection != collection.strip()
            or len(collection.encode("utf-8")) > 120 or "$" in collection
            or any(ord(c) < 32 for c in collection)
            or collection.startswith(".") or collection.endswith(".") or ".." in collection):
        raise MongoDBError("Invalid MongoDB collection name (1-120 UTF-8 bytes, no '$' or empty components).")
    return collection


def validate_limit(limit=DEFAULT_LIMIT):
    if type(limit) is not int or not 1 <= limit <= MAX_RESULTS:
        raise MongoDBError(f"limit must be an integer between 1 and {MAX_RESULTS}.")
    return limit


def _validate_json(value, depth=0):
    if depth > MAX_DEPTH:
        raise MongoDBError(f"MongoDB arguments may be nested at most {MAX_DEPTH} levels.")
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str or "\x00" in key:
                raise MongoDBError("MongoDB argument keys must be strings without null bytes.")
            if key in BLOCKED_OPERATORS:
                raise MongoDBError(f"Operator '{key}' is not allowed: MongoDB access is read-only and JavaScript is disabled.")
            _validate_json(item, depth + 1)
    elif type(value) is list:
        for item in value:
            _validate_json(item, depth + 1)
    elif value is None or type(value) in (str, bool):
        return
    elif type(value) is int and -(2**63) <= value < 2**63:
        return
    elif type(value) is float and math.isfinite(value):
        return
    else:
        raise MongoDBError("MongoDB arguments must contain JSON values and finite, BSON-compatible numbers only.")


def _validate_input(value):
    _validate_json(value)
    if len(json.dumps(value, ensure_ascii=True).encode("utf-8")) > MAX_INPUT_BYTES:
        raise MongoDBError("MongoDB arguments exceed the 64 KiB input limit.")


def _decode_literals(value):
    """Only these Extended JSON literals are accepted; never decode BSON Code."""
    if isinstance(value, list):
        return [_decode_literals(item) for item in value]
    if isinstance(value, dict):
        try:
            if set(value) == {"$oid"}:
                if type(value["$oid"]) is not str:
                    raise ValueError("ObjectId requires a string")
                return ObjectId(value["$oid"])
            if set(value) == {"$date"}:
                return datetime.fromisoformat(value["$date"])
            if set(value) == {"$numberDecimal"}:
                return Decimal128(value["$numberDecimal"])
        except Exception:
            raise MongoDBError("Invalid Extended JSON literal; use $oid, an ISO 8601 $date, or a string $numberDecimal.") from None
        return {key: _decode_literals(item) for key, item in value.items()}
    return value


def validate_query(query=None):
    if query is None:
        return {}
    if type(query) is not dict:
        raise MongoDBError("query must be a JSON object.")
    _validate_input(query)
    return _decode_literals(query)


def _validate_field(field):
    if (type(field) is not str or not field or field.startswith("$")
            or "\x00" in field or any(not part for part in field.split("."))):
        raise MongoDBError("Field names must be non-empty paths without a leading '$' or null bytes.")


def validate_projection(projection=None):
    if projection is None:
        return None
    if type(projection) is not dict:
        raise MongoDBError("projection must be an object mapping field names to 0 or 1.")
    _validate_input(projection)
    modes = set()
    for field, value in projection.items():
        _validate_field(field)
        if type(value) not in (int, bool) or value not in (0, 1):
            raise MongoDBError("projection values must be 0 or 1.")
        if field != "_id":
            modes.add(value)
    if len(modes) > 1:
        raise MongoDBError("projection cannot mix inclusion and exclusion, except for _id.")
    return dict(projection)


def validate_sort(sort=None):
    if sort is None:
        return None
    if type(sort) is not dict or not 1 <= len(sort) <= 32:
        raise MongoDBError("sort must be an object with 1-32 fields mapped to 1 or -1.")
    _validate_input(sort)
    for field, direction in sort.items():
        _validate_field(field)
        if type(direction) is not int or direction not in (-1, 1):
            raise MongoDBError("sort directions must be 1 (ascending) or -1 (descending).")
    return list(sort.items())


def validate_pipeline(pipeline):
    if type(pipeline) is not list or len(pipeline) > MAX_PIPELINE_STAGES:
        raise MongoDBError(f"pipeline must be an array of at most {MAX_PIPELINE_STAGES} stages.")
    for stage in pipeline:
        if type(stage) is not dict or len(stage) != 1:
            raise MongoDBError("Each aggregation stage must be an object with exactly one operator.")
        name, body = next(iter(stage.items()))
        if name in ("$out", "$merge"):
            raise MongoDBError(f"Aggregation stage '{name}' is not allowed because MongoDB access is read-only.")
        if name not in ALLOWED_STAGES:
            raise MongoDBError("Aggregation stage is not allowed. Allowed stages: " + ", ".join(sorted(ALLOWED_STAGES)) + ".")
        if name in {"$limit", "$skip"}:
            minimum = 1 if name == "$limit" else 0
            if type(body) is not int or not minimum <= body <= 1_000_000:
                raise MongoDBError(f"{name} must be an integer between {minimum} and 1000000.")
        elif name == "$count":
            _validate_field(body)
            if "." in body:
                raise MongoDBError("$count requires a field name without dots.")
        elif name == "$unwind":
            if type(body) is str:
                path = body
            elif type(body) is dict and set(body) <= {"path", "includeArrayIndex", "preserveNullAndEmptyArrays"}:
                path = body.get("path")
                if "preserveNullAndEmptyArrays" in body and type(body["preserveNullAndEmptyArrays"]) is not bool:
                    raise MongoDBError("$unwind preserveNullAndEmptyArrays must be boolean.")
                if "includeArrayIndex" in body:
                    _validate_field(body["includeArrayIndex"])
            else:
                raise MongoDBError("$unwind requires a field path or a valid options object.")
            if type(path) is not str or not path.startswith("$"):
                raise MongoDBError("$unwind path must start with '$'.")
            _validate_field(path[1:])
        elif type(body) is not dict:
            raise MongoDBError(f"{name} requires a JSON object.")
        elif name == "$sort":
            validate_sort(body)
        elif name == "$group" and "_id" not in body:
            raise MongoDBError("$group requires an _id expression (null groups all documents).")
    _validate_input(pipeline)  # Includes expressions, arrays, and nested filters.
    # A terminal cap also covers pipelines that expand documents using $unwind.
    return _decode_literals(pipeline) + [{"$limit": MAX_RESULTS}]


def _safe_operation(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        try:
            with timeout(10):
                return method(*args, **kwargs)
        except PyMongoError as exc:
            if isinstance(exc, OperationFailure) and exc.code in (13, 18):
                message = "MongoDB authentication or read permission failed. Check the server credentials and database role."
            elif exc.timeout:
                message = "MongoDB operation timed out. Check connectivity or simplify the query."
            else:
                message = "MongoDB operation failed. Check connectivity, read permissions, and query syntax."
            # Driver errors can include connection strings or server details.
            raise MongoDBError(message) from None
    return wrapped


def _read_documents(cursor, limit):
    rows, size = [], 0
    with cursor:
        for document in islice(cursor, limit):
            size += len(json.dumps(to_jsonable(document), allow_nan=False).encode("utf-8"))
            if size > MAX_RESULT_BYTES:
                raise MongoDBError("MongoDB results exceed 1 MiB. Use a smaller limit or a projection to select fewer fields.")
            rows.append(document)
    return rows


class MongoDB:
    """One lazy MongoClient per instance, reused for the lifetime of the MCP process."""

    def __init__(self):
        self._client = None
        self._lock = Lock()

    def _get_client(self):
        with self._lock:
            if self._client is None:
                uri = os.getenv("MONGODB_URI", "").strip()
                if not uri:
                    raise MongoDBError("MONGODB_URI is not configured. Set it in the server environment or .env file.")
                if not uri.startswith(("mongodb://", "mongodb+srv://")):
                    raise MongoDBError("Invalid MONGODB_URI. Use a mongodb:// or mongodb+srv:// connection string.")
                try:
                    # Invalid URI option warnings may contain values from the URI.
                    with warnings.catch_warnings():
                        warnings.simplefilter("error")
                        self._client = MongoClient(
                            uri, connect=False, tz_aware=True,
                            serverSelectionTimeoutMS=MAX_TIME_MS,
                            connectTimeoutMS=MAX_TIME_MS, socketTimeoutMS=MAX_TIME_MS,
                            timeoutMS=10000, maxPoolSize=10, appname="GlintMesh-MongoDB",
                        )
                except Exception:
                    raise MongoDBError("MongoDB connection configuration failed. Check MONGODB_URI and Atlas DNS/TLS settings.") from None
            return self._client

    def close(self):
        with self._lock:
            if self._client is not None:
                self._client.close()
                self._client = None

    @_safe_operation
    def ping(self):
        self._get_client().admin.command("ping", maxTimeMS=MAX_TIME_MS)
        return {"ok": True, "message": "MongoDB connection successful"}

    @_safe_operation
    def list_databases(self):
        cursor = self._get_client().list_databases(
            nameOnly=True, authorizedDatabases=True, maxTimeMS=MAX_TIME_MS,
        )
        rows = _read_documents(cursor, MAX_RESULTS + 1)
        return {"databases": [row["name"] for row in rows[:MAX_RESULTS]], "truncated": len(rows) > MAX_RESULTS}

    @_safe_operation
    def list_collections(self, database=None):
        database = validate_database(database)
        cursor = self._get_client()[database].list_collections(
            nameOnly=True, authorizedCollections=True, maxTimeMS=MAX_TIME_MS,
        )
        rows = _read_documents(cursor, MAX_RESULTS + 1)
        return {"database": database, "collections": [row["name"] for row in rows[:MAX_RESULTS]],
                "truncated": len(rows) > MAX_RESULTS}

    @_safe_operation
    def find(self, collection, database=None, query=None, projection=None, sort=None, limit=DEFAULT_LIMIT):
        database, collection = validate_database(database), validate_collection(collection)
        query, projection = validate_query(query), validate_projection(projection)
        sort, limit = validate_sort(sort), validate_limit(limit)
        cursor = self._get_client()[database][collection].find(
            query, projection=projection, sort=sort, limit=limit,
            max_time_ms=MAX_TIME_MS, batch_size=limit,
        )
        rows = _read_documents(cursor, limit)
        return {"database": database, "collection": collection, "documents": to_jsonable(rows),
                "returned": len(rows), "limit": limit, "limit_reached": len(rows) == limit}

    @_safe_operation
    def count(self, collection, database=None, query=None):
        database, collection = validate_database(database), validate_collection(collection)
        query = validate_query(query)
        count = self._get_client()[database][collection].count_documents(query, maxTimeMS=MAX_TIME_MS)
        return {"database": database, "collection": collection, "count": count}

    @_safe_operation
    def aggregate(self, collection, pipeline, database=None):
        database, collection = validate_database(database), validate_collection(collection)
        pipeline = validate_pipeline(pipeline)
        cursor = self._get_client()[database][collection].aggregate(
            pipeline, maxTimeMS=MAX_TIME_MS, allowDiskUse=False, batchSize=MAX_RESULTS,
        )
        rows = _read_documents(cursor, MAX_RESULTS)
        return {"database": database, "collection": collection, "documents": to_jsonable(rows),
                "returned": len(rows), "limit": MAX_RESULTS, "limit_reached": len(rows) == MAX_RESULTS}

    @_safe_operation
    def get_schema(self, collection, database=None):
        database, collection = validate_database(database), validate_collection(collection)
        cursor = self._get_client()[database][collection].find(
            {}, limit=SCHEMA_SAMPLE_SIZE, max_time_ms=MAX_TIME_MS, batch_size=SCHEMA_SAMPLE_SIZE,
        )
        rows = _read_documents(cursor, SCHEMA_SAMPLE_SIZE)
        fields = {}

        def inspect_value(value, path, depth=0):
            if path:
                fields.setdefault(path, set()).add(type(value).__name__ if value is not None else "null")
            if depth >= MAX_DEPTH:
                return
            if isinstance(value, dict):
                for key, item in value.items():
                    inspect_value(item, f"{path}.{key}" if path else key, depth + 1)
            elif isinstance(value, list):
                for item in value[:SCHEMA_SAMPLE_SIZE]:
                    inspect_value(item, path + "[]", depth + 1)

        for row in rows:
            inspect_value(row, "")
        return {"database": database, "collection": collection, "sample_size": len(rows),
                "approximate": True, "fields": [
                    {"field": name, "types": sorted(types)} for name, types in sorted(fields.items())
                ]}
