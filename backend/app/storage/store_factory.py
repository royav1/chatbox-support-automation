import os
from typing import Any

from app.storage.redis_memory import RedisMemoryStore
from app.storage.memory import MemoryStore

USE_REDIS = os.getenv("USE_REDIS", "1") == "1"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "7200"))

# Single app-wide store instance (same as you had in chat_routes.py)
if USE_REDIS:
    _memory = RedisMemoryStore(redis_url=REDIS_URL, ttl_seconds=TTL_SECONDS)
else:
    _memory = MemoryStore(ttl_seconds=TTL_SECONDS)


def get_memory() -> Any:
    return _memory


def cleanup_if_supported(memory: Any) -> int:
    cleanup = getattr(memory, "cleanup_expired", None)
    if callable(cleanup):
        return int(cleanup())
    return 0
