import sys
import asyncio
import pyTON

from fastapi import FastAPI, Depends, status as S
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from starlette.exceptions import HTTPException as StarletteHTTPException

from pyTON.schemas import TonResponse    
from pyTON.api.deps.ton import settings_dep, cache_manager_dep, tonlib_dep
from pyTON.api.deps.apikey import api_key_dep
from pyTON.api.api_v3.endpoints import common, status

from pytonlib import TonlibException

from loguru import logger


# main service
description = """
This API enables HTTP access to TON blockchain - getting accounts and wallets information, looking up blocks and transactions, sending messages to the blockchain, calling get methods of smart contracts, and more.

In addition to REST API, all methods are available through [JSON-RPC endpoint](#json%20rpc)  with `method` equal to method name and `params` passed as a dictionary.

The response contains a JSON object, which always has a boolean field `ok` and either `error` or `result`. If `ok` equals true, the request was successful and the result of the query can be found in the `result` field. In case of an unsuccessful request, `ok` equals false and the error is explained in the `error`.

API Key should be sent either as `api_key` query parameter or `X-API-Key` header.
"""

tags_metadata = [
    {
        "name": "accounts",
        "description": "Information about accounts.",
    },
    {
        "name": "blocks",
        "description": "Information about blocks.",
    },
    {
        "name": "transactions",
        "description": "Fetching and locating transactions.",
    },
    {   
        "name": "get config",
        "description": "Get blockchain config"
    },
    {
        "name": "run method",
        "description": "Run get method of smart contract.",
    },
    {
        "name": "send",
        "description": "Send data to blockchain.",
    },
    {
        "name": "json rpc",
        "description": "JSON-RPC endpoint.",
    },
]

app = FastAPI(
    title="TON HTTP API (v3)",
    description=description,
    version=pyTON.__version__,
    docs_url='/',
    responses={
        422: {'description': 'Validation Error'},
        504: {'description': 'Lite Server Timeout'}
    },
    openapi_tags=tags_metadata,
    dependencies=[Depends(api_key_dep)]
)


# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc):
    res = TonResponse(ok=False, error=str(exc.detail), code=exc.status_code)
    return JSONResponse(res.dict(exclude_none=True), status_code=res.code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    res = TonResponse(ok=False, error=f"Validation error: {exc}", code=S.HTTP_422_UNPROCESSABLE_ENTITY)
    return JSONResponse(res.dict(exclude_none=True), status_code=S.HTTP_422_UNPROCESSABLE_ENTITY)


@app.exception_handler(asyncio.TimeoutError)
async def timeout_exception_handler(request, exc):
    res = TonResponse(ok=False, error="Liteserver timeout", code=S.HTTP_504_GATEWAY_TIMEOUT)
    return JSONResponse(res.dict(exclude_none=True), status_code=S.HTTP_504_GATEWAY_TIMEOUT)


@app.exception_handler(TonlibException)
async def tonlib_error_result_exception_handler(request, exc):
    res = TonResponse(ok=False, error=str(exc), code=S.HTTP_500_INTERNAL_SERVER_ERROR)
    return JSONResponse(res.dict(exclude_none=True), status_code=S.HTTP_500_INTERNAL_SERVER_ERROR)


@app.exception_handler(Exception)
async def fastapi_generic_exception_handler(request, exc):
    res = TonResponse(ok=False, error=str(exc), code=S.HTTP_503_SERVICE_UNAVAILABLE)
    return JSONResponse(res.dict(exclude_none=True), status_code=S.HTTP_503_SERVICE_UNAVAILABLE)

app.include_router(common.router)
app.include_router(status.router, include_in_schema=True, tags=['system'])  # FIXME: remove from schema
