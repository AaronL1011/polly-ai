import hashlib
import pickle
from typing import Any

import redis.asyncio as redis

from democrata_server.domain.rag.entities import Query


class RedisCache:
    def __init__(self, url: str = "redis://localhost:6379/0"):
        self.client = redis.from_url(url, decode_responses=False)

    async def get(self, key: str) -> Any | None:
        data = await self.client.get(key)
        if data is None:
            return None
        return pickle.loads(data)

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        data = pickle.dumps(value)
        if ttl_seconds:
            await self.client.setex(key, ttl_seconds, data)
        else:
            await self.client.set(key, data)

    async def delete(self, key: str) -> None:
        await self.client.delete(key)

    def query_key(self, query: Query) -> str:
        key_parts = [query.text]
        if query.filters:
            key_parts.append(str(query.filters))
        key_str = "|".join(key_parts)
        return f"rag:query:{hashlib.sha256(key_str.encode()).hexdigest()[:16]}"

    async def close(self) -> None:
        await self.client.close()
