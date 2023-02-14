from xml.etree.ElementInclude import include
from fastapi import APIRouter, Depends

from pyTON.core.tonlib.manager import TonlibManager
from pyTON.schemas import TonResponse
from pyTON.api.deps.ton import tonlib_dep


router = APIRouter()


@router.get('/workers')
async def get_workers(tonlib: TonlibManager=Depends(tonlib_dep)):
    return tonlib.get_workers_state()


@router.get('/healthcheck')
async def healthcheck():
    return 'OK'
