import inject
import traceback

from collections.abc import Mapping
from abc import abstractmethod

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.responses import Response, StreamingResponse
from starlette.types import Message

from pymongo import MongoClient
from datetime import datetime
from functools import wraps
from json import loads

from pyTON.models import TonResponse, TonlibClientResult
from pyTON.settings import Settings, MongoDBSettings, LoggingSettings, MongoDBLoggingSettings

from typing import Optional

from loguru import logger


class LoggingManager:
    def log_liteserver_task(self, task_result: TonlibClientResult, *args, **kwargs) -> None:
        pass

    def log_request_details(self, request_details, *args, **kwargs) -> None:
        pass

    def log_request_stats(self, request_stats, *args, **kwargs) -> None:
        pass

    def log_worker_status(self, worker_stats, *args, **kwargs) -> None:
        pass


class DisabledLoggingManager(LoggingManager):
    pass


class MongoLoggingManager(LoggingManager):
    def __init__(self, logging_settings: MongoDBLoggingSettings, *args, **kwargs):
        self.mongo_client = MongoClient(host=logging_settings.mongodb.host,
                                        port=logging_settings.mongodb.port,
                                        username=logging_settings.mongodb.username,
                                        password=logging_settings.mongodb.password)
        self.database = logging_settings.mongodb.database
        self.mongo_client[self.database]['requests'].create_index('timestamp', expireAfterSeconds=logging_settings.record_ttl)
        self.mongo_client[self.database]['liteserver_tasks'].create_index('timestamp', expireAfterSeconds=logging_settings.record_ttl)
        self.mongo_client[self.database]['request_stats'].create_index('timestamp', expireAfterSeconds=logging_settings.record_ttl)

    def log_liteserver_task(self, task_result: TonlibClientResult, *args, **kwargs):
        res_type = None
        if isinstance(task_result.result, Mapping):
            res_type = task_result.result.get('@type', 'unknown') if task_result.result else 'error'
        else:
            result_type = 'list'
        details = {}
        if res_type == 'error' or res_type == 'unknown':
            details['params'] = [str(p) for p in task_result.params]
            details['result'] = task_result.result
            details['exception'] = str(task_result.exception)
        
        rec = {
            'timestamp': datetime.utcnow(),
            'elapsed': task_result.elapsed_time,
            'task_id': task_result.task_id,
            'method': task_result.method,
            'liteserver_info': task_result.liteserver_info,
            'result_type': res_type,
            'details': details,
        }
        self.mongo_client[self.database]['liteserver_tasks'].insert_one(rec)
        logger.info("Received result of type: {result_type} task_id: {task_id} method: {method}", **rec)

    def log_request_details(self, request_details, *args, **kwargs) -> None:
        self.mongo_client[self.database]['requests'].insert_one(request_details)

    def log_request_stats(self, request_stats, *args, **kwargs) -> None:
        self.mongo_client[self.database]['request_stats'].insert_one(request_stats)

    def log_worker_status(self, worker_stats, *args, **kwargs) -> None:
        pass


# For unknown reason FastAPI can't handle generic Exception with exception_handler(...)
# https://github.com/tiangolo/fastapi/issues/2750
# As workaround - catch and handle this exception in the middleware.
def generic_exception_handler(exc):
    res = TonResponse(ok=False, error=str(exc), code=status.HTTP_503_SERVICE_UNAVAILABLE)
    return JSONResponse(res.dict(exclude_none=True), status_code=status.HTTP_503_SERVICE_UNAVAILABLE)


def generic_http_exception_handler(exc):
    res = TonResponse(ok=False, error=str(exc.detail), code=exc.status_code)
    return JSONResponse(res.dict(exclude_none=True), status_code=res.code)


class LoggerMiddleware(BaseHTTPMiddleware):
    def __init__(self, 
                 app, 
                 settings: Settings,
                 logging_manager: LoggingManager):
        super(LoggerMiddleware, self).__init__(app)
        self.settings = settings
        self.logging_manager = logging_manager
        logger.info(f'Logger MiddleWare got settings={settings} and logging_manager={LoggingManager}')

    # Workaround for https://github.com/tiangolo/fastapi/issues/394#issuecomment-927272627
    async def set_body(self, request: Request):
        receive_ = await request._receive()

        async def receive() -> Message:
            return receive_

        request._receive = receive

    async def call_and_log(self, request: Request, call_next):
        if not self.settings.logging.enabled:
            return await call_next(request)

        start = datetime.utcnow()

        response = await call_next(request)

        if isinstance(response, StreamingResponse):
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
        if self.settings.logging.log_successful_requests or response.status_code != status.HTTP_200_OK:
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
            try:
                self.logging_manager.log_request_details(record)
            except:
                logger.critical(f"Error while logging request details: {traceback.format_exc()}")

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
            'from_ip': request.client.host or "?",
            'referer': request.headers.get('referer', '?'),
            'origin': request.headers.get('origin', '?'),
            'api_key': request.query_params.get('api_key') or request.headers.get('X-API-Key'),
            'url': url,
            'status_code': response.status_code,
            'elapsed': elapsed
        }

        try:
            self.logging_manager.log_request_stats(stat_record)
        except:
            logger.critical(f"Error while logging request stats: {traceback.format_exc()}")
        return response

    async def dispatch(self, request: Request, call_next):
        await self.set_body(request)
        body = await request.body()

        submiddlewares = [self.call_and_log]

        async def call_submiddlewares(request):
            if len(submiddlewares) == 0:
                return await call_next(request)
            cur_submiddleware = submiddlewares.pop(0)
            return await cur_submiddleware(request, call_submiddlewares)

        try:
            response = await call_submiddlewares(request)
        except StarletteHTTPException as ex:
            response = generic_http_exception_handler(ex)
        except Exception as ex:
            response = generic_exception_handler(ex)

        return response
