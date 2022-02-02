from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.responses import Response
from starlette.types import Message

from pymongo import MongoClient
from datetime import datetime
from functools import wraps
from json import loads

from pyTON.models import TonResponse
from config import settings

from loguru import logger


def to_mongodb(collection, creds):
    with open(creds['password_file'], 'r') as f:
        password = f.read()
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            client = MongoClient(host=creds["host"], 
                                 port=creds["port"],
                                 username=creds["username"],
                                 password=password)
            db = creds['database']
            result = func(*args, **kwargs)
            client[db][collection].insert_one(result)
            return result
        return wrapper
    return decorator


# For unknown reason FastAPI can't handle generic Exception with exception_handler(...)
# https://github.com/tiangolo/fastapi/issues/2750
# As workaround - catch and handle this exception in MongoLoggerMiddleware.
def generic_exception_handler(exc):
    res = TonResponse(ok=False, error=str(exc), code=status.HTTP_503_SERVICE_UNAVAILABLE)
    return JSONResponse(res.dict(exclude_none=True), status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    

class MongoLoggerMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, host, port, username, password_file, database):
        super().__init__(app)
        with open(password_file, 'r') as f:
            password = f.read()
        self.client = MongoClient(host=host, 
                                  port=port,
                                  username=username,
                                  password=password)
        self.database = database

    # Workaround for https://github.com/tiangolo/fastapi/issues/394
    async def set_body(self, request: Request):
        receive_ = await request._receive()

        async def receive() -> Message:
            return receive_

        request._receive = receive

    async def dispatch(self, request: Request, call_next):
        start = datetime.utcnow()

        await self.set_body(request)
        body = await request.body()

        response = None
        try:
            response = await call_next(request)
        except Exception as ex:
            response = generic_exception_handler(ex)
        else:
            response_headers = dict(response.headers.items())
            response_body = b''
            async for chunk in response.body_iterator:
                response_body += chunk
            response = Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )

        end = datetime.utcnow()
        elapsed = (end - start).total_seconds()

        # Log only error response body
        response_body = response.body if response.status_code != 200 else None

        # full record in case of error
        if settings.logs.successful_requests or response.status_code != status.HTTP_200_OK:
            record = {
                'timestamp': start,
                'elapsed': elapsed,
                'request': {
                    'method': request.method,
                    'headers': request.headers,
                    'url': request.url.path,
                    'query_params': request.query_params.__dict__,
                    'path_params': request.path_params,
                    'body': body
                },
                'response': {
                    'status_code': response.status_code,
                    'headers': response.headers,
                    'body': response_body
                }
            }
        
            # FIXME: can this slow down response time?
            self.client[self.database].requests.insert_one(record)

        # statistics record
        url = request.url.path
        if url.endswith('jsonRPC'):
            try:
                body_dict = loads(body)
                url += f'?method={body_dict["method"]}'
            except Exception as ee:
                logger.critical(ee)
        stat_record = {
            'timestamp': datetime.now(),
            'from_ip': request.headers.get('x-real-ip', '?'),
            'referer': request.headers.get('referer', '?'),
            'origin': request.headers.get('origin', '?'),
            'url': url,
            'status_code': response.status_code,
            'elapsed': elapsed
        }

        # FIXME: can this slow down response time?
        self.client[self.database].request_stats.insert_one(stat_record)

        return response
