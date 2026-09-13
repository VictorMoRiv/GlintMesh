"""MongoDB connection module for GlintMesh.

Falls back gracefully to file-based storage if MongoDB is unavailable.
Set MONGODB_URI in .env to enable MongoDB (e.g. mongodb+srv://... for Atlas).
"""

import os
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

MONGODB_URI = os.getenv("MONGODB_URI", "")
MONGODB_DB = os.getenv("MONGODB_DB", "glintmesh")

client: AsyncIOMotorClient | None = None
db = None
MONGODB_AVAILABLE = False


async def connect_db():
    """Initialize MongoDB connection. Falls back gracefully if unavailable."""
    global client, db, MONGODB_AVAILABLE
    if not MONGODB_URI:
        print("No MONGODB_URI set. Using file-based storage.")
        return
    try:
        client = AsyncIOMotorClient(MONGODB_URI, serverSelectionTimeoutMS=3000)
        # Force a connection test
        await client.admin.command("ping")
        db = client[MONGODB_DB]

        await db.users.create_indexes([
            IndexModel([("username", ASCENDING)], unique=True)
        ])
        await db.datasets.create_indexes([
            IndexModel([("dataset_id", ASCENDING)], unique=True)
        ])
        MONGODB_AVAILABLE = True
        print(f"Connected to MongoDB: {MONGODB_DB}")
    except Exception as exc:
        print(f"MongoDB unavailable ({exc}). Using file-based storage.")
        client = None
        db = None
        MONGODB_AVAILABLE = False


async def close_db():
    """Close MongoDB connection."""
    global client
    if client:
        client.close()
        print("MongoDB connection closed")


def get_db():
    return db


def users_collection():
    return db["users"] if db else None


def datasets_collection():
    return db["datasets"] if db else None
