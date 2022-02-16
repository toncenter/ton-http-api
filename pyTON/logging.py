from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.responses import Response, StreamingResponse
from starlette.types import Message

from pymongo import MongoClient
from datetime import datetime
from functools import wraps
from json import loads

from limits import RateLimitItem, parse_many
from limits.aio.storage import RedisStorage
from limits.aio.strategies import FixedWindowRateLimiter

from pyTON.api_key_manager import per_method_limits, total_limits, api_key_from_request, api_key_header, api_key_query
from pyTON.models import TonResponse
from config import settings

from loguru import logger

# Create mongo_client and mongo_db
if settings.logs.enabled:
    with open(settings.logs.mongodb.password_file, 'r') as f:
        mongo_password = f.read()
    mongo_client = MongoClient(host=settings.logs.mongodb.host, 
                         port=settings.logs.mongodb.port,
                         username=settings.logs.mongodb.username,
                         password=mongo_password)
    mongo_db = settings.logs.mongodb.database
else:
    mongo_client = None

def to_mongodb(collection):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if mongo_client:
                mongo_client[mongo_db][collection].insert_one(result)
            return result
        return wrapper
    return decorator


# For unknown reason FastAPI can't handle generic Exception with exception_handler(...)
# https://github.com/tiangolo/fastapi/issues/2750
# As workaround - catch and handle this exception in the middleware.
def generic_exception_handler(exc):
    res = TonResponse(ok=False, error=str(exc), code=status.HTTP_503_SERVICE_UNAVAILABLE)
    return JSONResponse(res.dict(exclude_none=True), status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    

class LoggerAndRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, endpoints, temp_disable_ratelimit=False):
        super().__init__(app)

        self.temp_disable_ratelimit = temp_disable_ratelimit

        if settings.ratelimit.enabled:
            self.endpoints = endpoints
            self.rate_limit_storage = RedisStorage(f"redis://{settings.ratelimit.redis.endpoint}:{settings.ratelimit.redis.port}")
            self.fixed_window = FixedWindowRateLimiter(self.rate_limit_storage)

    # Workaround for https://github.com/tiangolo/fastapi/issues/394#issuecomment-927272627
    async def set_body(self, request: Request):
        receive_ = await request._receive()

        async def receive() -> Message:
            return receive_

        request._receive = receive

    async def rate_limit_and_call(self, request: Request, call_next):
        if not settings.ratelimit.enabled or self.temp_disable_ratelimit:
            return await call_next(request)

        path_comps = list(filter(None, request.url.path.split('/')))
        if len(path_comps) == 0:
            return await call_next(request)
        endpoint = path_comps[-1]
        if endpoint == 'jsonRPC':
            body = await request.json()
            endpoint = body.get('method')

        if endpoint not in self.endpoints:
            return await call_next(request)

        keys = api_key_from_request(request)
        if not isinstance(keys, list):
            keys = [keys]

        failed_limit = None
        for key in keys:
            # Per method limits
            per_method_limits_str = per_method_limits(endpoint, key)
            if per_method_limits_str == 'unlimited':
                per_method_limits_ = []
            else:    
                per_method_limits_ = parse_many(per_method_limits_str)

            for limit in per_method_limits_:
                identifiers = [endpoint, key]
                if not await self.fixed_window.hit(limit, *identifiers):
                    failed_limit = limit
                    break
            if failed_limit:
                break

            # Total limits
            total_limits_str = total_limits(key)
            if total_limits_str == 'unlimited':
                total_limits_ = []
            else:    
                total_limits_ = parse_many(total_limits_str)

            for limit in total_limits_:
                identifiers = [key]
                if not await self.fixed_window.hit(limit, *identifiers):
                    failed_limit = limit
                    break
            if failed_limit:
                break

        if failed_limit:
            res = TonResponse(ok=False, error=f"Rate limit exceeded: {failed_limit}", code=429)
            return JSONResponse(res.dict(exclude_none=True), status_code=res.code)
        result = await call_next(request)
        return result

    async def call_and_log(self, request: Request, call_next):
        if not settings.logs.enabled:
            return await call_next(request)

        start = datetime.utcnow()

        response = await call_next(request)

        if isinstance(response, StreamingResponse):
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

        request_body = await request.body()

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
                    'body': request_body
                },
                'response': {
                    'status_code': response.status_code,
                    'headers': response.headers,
                    'body': response_body
                }
            }
        
            mongo_client[mongo_db].requests.insert_one(record)

        # statistics record
        url = request.url.path
        if url.endswith('jsonRPC'):
            try:
                body_dict = loads(request_body)
                url += f'?method={body_dict["method"]}'
            except Exception as ee:
                logger.critical(ee)
        stat_record = {
            'timestamp': datetime.now(),
            'from_ip': request.headers.get('x-real-ip', '?'),
            'referer': request.headers.get('referer', '?'),
            'origin': request.headers.get('origin', '?'),
            'api_key': request.query_params.get(api_key_query.model.name) or request.headers.get(api_key_header.model.name),
            'url': url,
            'status_code': response.status_code,
            'elapsed': elapsed
        }

        mongo_client[mongo_db].request_stats.insert_one(stat_record)

        return response

    async def dispatch(self, request: Request, call_next):
        await self.set_body(request)
        body = await request.body()

        submiddlewares = [self.call_and_log, self.rate_limit_and_call]

        async def call_submiddlewares(request):
            if len(submiddlewares) == 0:
                return await call_next(request)
            cur_submiddleware = submiddlewares.pop(0)
            return await cur_submiddleware(request, call_submiddlewares)

        try:
            response = await call_submiddlewares(request)
        except Exception as ex:
            response = generic_exception_handler(ex)

        return response
