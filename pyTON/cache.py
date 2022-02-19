import aioredis
import ring
from ring.func.asyncio import Aioredis2Storage
from config import settings

class TonlibResultRedisStorage(Aioredis2Storage):
    async def set(self, key, value, expire=...):
        if value.get('@type', 'error') == 'error':
            return None
        return await super().set(key, value, expire)

def redis_cached(expire, check_error=True):
    if settings.cache.enabled:
        cache_redis = aioredis.from_url(f"redis://{settings.cache.redis.endpoint}:{settings.cache.redis.port}")
        storage_class = TonlibResultRedisStorage if check_error else Aioredis2Storage
        def g(func):
            return ring.aioredis(cache_redis, coder='pickle', expire=expire, storage_class=storage_class)(func)
    else:
        def g(func):
            return func
    return g
