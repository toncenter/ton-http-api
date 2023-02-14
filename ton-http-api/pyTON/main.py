import sys
import pyTON

from fastapi import FastAPI

from pyTON.api.api_v2.app import app as app_v2
from pyTON.api.api_v3.app import app as app_v3
from pyTON.api.deps.ton import settings_dep, cache_manager_dep, tonlib_dep

from loguru import logger


settings = settings_dep()
if settings.webserver.enable_v3:
    app = FastAPI(version=pyTON.__version__)
    app.mount('/api/v2', app_v2, name='api_v2')
    app.mount('/api/v3', app_v3, name='api_v3')
elif settings.webserver.api_root_path:
    app = FastAPI(version=pyTON.__version__)
    app.mount(settings.webserver.api_root_path, app_v2, name='api_v2')
else:
    app = app_v2


@app.on_event("startup")
async def startup():
    settings = settings_dep()
    
    # prepare logger
    logger.remove()
    logger.add(sys.stdout, level=settings.logging.level, enqueue=True, serialize=settings.logging.jsonify)
    
    # prepare tonlib
    cache_manager_dep.init(settings)
    cache_manager = cache_manager_dep()

    await tonlib_dep.init(settings, cache_manager)


@app.on_event("shutdown")
async def shutdown_event():
    try:
        await tonlib_dep.tonlib_manager.shutdown()
    except:
        logger.error('Failed to shutdown TonlibManager')
