from pyTON.core.tonlib.manager import TonlibManager
from pyTON.core.cache import DisabledCacheManager
from pyTON.core.cache import CacheManager, RedisCacheManager
from pyTON.core.settings import RedisCacheSettings, Settings

from fastapi import Depends

import asyncio


class SettingsDep:
    def __init__(self):
        self.settings = None

    def init(self):
        self.settings = Settings.from_environment()
        return self
    
    def __call__(self):
        if self.settings is None:
            self.init()
        return self.settings


settings_dep = SettingsDep()


class CacheManagerDep:
    def __init__(self):
        self.cache_manager = None

    def init(self, settings):
        if settings.cache.enabled:
            if isinstance(settings.cache, RedisCacheSettings):
                self.cache_manager = RedisCacheManager(settings.cache)
            else:
                raise RuntimeError('Only Redis cache supported')
        else:
            self.cache_manager = DisabledCacheManager()
        return self

    def __call__(self, settings: Settings=Depends(settings_dep)):
        if self.cache_manager is None:
            self.init(settings)
        return self.cache_manager


cache_manager_dep = CacheManagerDep()

class TonlibManagerDep:
    def __init__(self):
        self.tonlib_manager = None

    async def init(self, settings, cache_manager):
        loop = asyncio.get_running_loop()
        self.tonlib_manager = TonlibManager(tonlib_settings=settings.tonlib,
                                            dispatcher=None,
                                            cache_manager=cache_manager,
                                            loop=loop)
        await asyncio.sleep(2)
        return self
        
    async def __call__(self,
                 cache_manager: CacheManager=Depends(cache_manager_dep),
                 settings: Settings=Depends(settings_dep)):
        if self.tonlib_manager is None:
            await self.init(settings, cache_manager)
        return self.tonlib_manager


tonlib_dep = TonlibManagerDep()
