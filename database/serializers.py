"""Convert BSON values to plain, recursively JSON-serializable values."""

import json
import math
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from bson import Decimal128, ObjectId, json_util


def to_jsonable(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        # MongoDB stores UTC; PyMongo can return naive UTC datetimes.
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, (Decimal128, Decimal, UUID)):
        return str(value)
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    # Binary, Regex, Timestamp, MinKey, MaxKey, DBRef, etc.: Extended JSON.
    return json.loads(json_util.dumps(value))
