import redis.asyncio
import ring

from ring.func.asyncio import Aioredis2Storage
from pyTON.settings import RedisCacheSettings


class TonlibResultRedisStorage(Aioredis2Storage):
    async def set(self, key, value, expire=...):
        if value.get('@type', 'error') == 'error':
            return None
        return await super().set(key, value, expire)


class CacheManager:
    def cached(self, expire=0, check_error=True):
        pass


class DisabledCacheManager:
    def cached(self, expire=0, check_error=True):
        def g(func):
            def wrapper(*args, **kwargs):
                return func(*args, **kwargs)
            return wrapper
        return g


class RedisCacheManager:
    def __init__(self, cache_settings: RedisCacheSettings):
        self.cache_settings = cache_settings
        self.cache_redis = redis.asyncio.from_url(f"redis://{cache_settings.redis.endpoint}:{cache_settings.redis.port}")

    def cached(self, expire=0, check_error=True):
        storage_class = TonlibResultRedisStorage if check_error else Aioredis2Storage
        def g(func):
            return ring.aioredis(self.cache_redis, coder='pickle', expire=expire, storage_class=storage_class)(func)
        return g
